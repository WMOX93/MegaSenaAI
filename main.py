import os, json, threading, math
from datetime import datetime

import requests
import numpy as np

from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.spinner import Spinner
from kivy.uix.scrollview import ScrollView
from kivy.uix.progressbar import ProgressBar

API = 'https://servicebus2.caixa.gov.br/portaldeloterias/api/megasena'
BASE_DIR = os.path.dirname(__file__)
DATA_FILE = os.path.join(BASE_DIR, 'megasena.json')
MODEL_FILE = os.path.join(BASE_DIR, 'adaptive_model.json')


def api_json(url, timeout=20):
    r = requests.get(url, timeout=timeout, headers={'User-Agent': 'MegaSenaAI/3.1'})
    r.raise_for_status()
    return r.json()


def normalize_draw(j):
    nums = sorted(int(x) for x in j['listaDezenas'])
    if len(nums) != 6 or len(set(nums)) != 6:
        return None
    return {'concurso': int(j['numero']), 'data': j.get('dataApuracao', ''), 'nums': nums}


def fetch_initial_history(n=500):
    latest = api_json(API)
    last = int(latest['numero'])
    first = max(1, last - n + 1)
    rows = []
    for c in range(last, first - 1, -1):
        try:
            row = normalize_draw(api_json(f'{API}/{c}', timeout=15))
            if row:
                rows.append(row)
        except Exception:
            pass
    if not rows:
        raise RuntimeError('Não foi possível obter os concursos.')
    rows.sort(key=lambda x: x['concurso'])
    save_history(rows)
    return rows


def sync_history(max_history=1000):
    hist = load_history()
    latest = api_json(API)
    latest_no = int(latest['numero'])
    if not hist:
        return fetch_initial_history(max_history), True, latest_no
    last_local = max(int(r['concurso']) for r in hist)
    if latest_no <= last_local:
        return hist, False, last_local
    new_rows = []
    for c in range(last_local + 1, latest_no + 1):
        try:
            row = normalize_draw(api_json(f'{API}/{c}', timeout=15))
            if row:
                new_rows.append(row)
        except Exception:
            pass
    by_no = {int(r['concurso']): r for r in hist}
    for row in new_rows:
        by_no[int(row['concurso'])] = row
    hist = sorted(by_no.values(), key=lambda x: x['concurso'])[-max_history:]
    save_history(hist)
    return hist, bool(new_rows), latest_no


def save_history(hist):
    with open(DATA_FILE, 'w', encoding='utf-8') as f:
        json.dump(hist, f, ensure_ascii=False)


def load_history():
    if not os.path.exists(DATA_FILE): return []
    with open(DATA_FILE, encoding='utf-8') as f: return json.load(f)


def feature_vector(past, num):
    total = len(past)
    if total == 0: return np.zeros(6, dtype=float)
    present = np.array([num in r['nums'] for r in past], dtype=float)
    windows = [10, 20, 50, 100, 200]
    recent = [float(present[-min(w, total):].mean()) for w in windows]
    delay = next((i for i, x in enumerate(present[::-1]) if x > 0), total)
    return np.array([float(present.mean()), *recent, min(delay / max(total, 1), 1.0)], dtype=float)


def build_learning_set(hist, min_history=30, max_examples=1200):
    X, y = [], []
    start = min(min_history, max(1, len(hist) - 1))
    indices = list(range(start, len(hist)))
    if len(indices) > max_examples: indices = indices[-max_examples:]
    for i in indices:
        past, target = hist[:i], set(hist[i]['nums'])
        for num in range(1, 61):
            X.append(feature_vector(past, num)); y.append(1.0 if num in target else 0.0)
    return np.asarray(X, dtype=float), np.asarray(y, dtype=float)


def fit_adaptive_model(hist):
    X, y = build_learning_set(hist)
    if len(X) < 60:
        return {'weights':[1,1,1,1,1,0.2], 'bias':0.0, 'trained_on':len(hist), 'trained_at':datetime.now().isoformat(timespec='seconds')}
    mean, std = X.mean(axis=0), X.std(axis=0); std[std < 1e-8] = 1.0
    Z, w, b = (X-mean)/std, np.zeros(X.shape[1]), 0.0
    for _ in range(220):
        p = 1.0/(1.0+np.exp(-np.clip(Z@w+b,-20,20))); err=p-y
        w -= 0.12*((Z.T@err)/len(y)+0.01*w); b -= 0.12*float(err.mean())
    raw_w=w/std; raw_b=b-float(np.sum(w*mean/std))
    return {'weights':raw_w.tolist(),'bias':raw_b,'mean':mean.tolist(),'std':std.tolist(),'trained_on':len(hist),'trained_at':datetime.now().isoformat(timespec='seconds')}


def save_model(model):
    with open(MODEL_FILE, 'w', encoding='utf-8') as f: json.dump(model, f, ensure_ascii=False, indent=2)


def load_model():
    if not os.path.exists(MODEL_FILE): return None
    try:
        with open(MODEL_FILE, encoding='utf-8') as f: return json.load(f)
    except Exception: return None


def adaptive_probabilities(hist, model=None):
    model = model or fit_adaptive_model(hist)
    weights, bias = np.asarray(model['weights'], dtype=float), float(model.get('bias',0.0))
    out=[]
    for num in range(1,61):
        x=feature_vector(hist,num); p=1.0/(1.0+math.exp(-float(np.clip(x@weights+bias,-20,20))))
        out.append((num,p,x))
    vals=np.array([x[1] for x in out]); lo,hi=float(vals.min()),float(vals.max())
    return sorted([{'numero':n,'model_prob':p,'score':100*(p-lo)/(hi-lo+1e-12),'features':x.tolist()} for n,p,x in out], key=lambda r:r['score'], reverse=True)


def game_score(game, ranking):
    mp={r['numero']:r['score'] for r in ranking}; ev=sum(x%2==0 for x in game); total=sum(game)
    decade=[sum(10*d+1<=x<=10*d+10 for x in game) for d in range(6)]
    parity=1.0 if 2<=ev<=4 else 0.6; sumscore=math.exp(-0.5*((total-183)/45)**2); spread=1.0 if max(decade)<=2 else 0.75
    return 100*(0.65*(sum(mp[x] for x in game)/6/100)+0.15*parity+0.10*sumscore+0.10*spread)


def generate_games(ranking,n_games=20):
    nums=np.array([r['numero'] for r in ranking]); p=np.array([max(r['score'],1e-3) for r in ranking],dtype=float); p/=p.sum(); rng=np.random.default_rng(); seen=set(); out=[]
    for _ in range(max(5000,n_games*1000)):
        g=tuple(sorted(rng.choice(nums,6,replace=False,p=p).tolist()))
        if g in seen: continue
        ev=sum(x%2==0 for x in g); total=sum(g); decades=[sum(10*d+1<=x<=10*d+10 for x in g) for d in range(6)]
        if not 1<=ev<=5 or not 80<=total<=280 or max(decades)>4: continue
        seen.add(g); out.append((game_score(g,ranking),g,total,ev))
        if len(out)>=n_games*4: break
    out.sort(reverse=True,key=lambda x:x[0]); return out[:n_games]


class MegaSenaApp(App):
    def build(self):
        self.title='Mega-Sena AI V3'; root=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8))
        root.add_widget(Label(text='[b]MEGA-SENA AI V3[/b]',markup=True,font_size=dp(22),size_hint_y=None,height=dp(45)))
        controls=GridLayout(cols=2,size_hint_y=None,height=dp(205),spacing=dp(6))
        controls.add_widget(Label(text='Histórico:')); self.conc=Spinner(text='1000',values=('100','300','500','1000'),size_hint_y=None,height=dp(42)); controls.add_widget(self.conc)
        controls.add_widget(Label(text='Jogos:')); self.ng=Spinner(text='20',values=('10','20','50','100'),size_hint_y=None,height=dp(42)); controls.add_widget(self.ng)
        self.update_btn=Button(text='ATUALIZAR AGORA',size_hint_y=None,height=dp(48)); self.update_btn.bind(on_release=self.run_analysis); controls.add_widget(self.update_btn)
        self.off_btn=Button(text='USAR DADOS SALVOS',size_hint_y=None,height=dp(48)); self.off_btn.bind(on_release=self.run_saved); controls.add_widget(self.off_btn); root.add_widget(controls)
        self.progress=ProgressBar(max=1,value=0,size_hint_y=None,height=dp(8)); root.add_widget(self.progress)
        scroll=ScrollView(); self.out=Label(text='Iniciando sincronização automática...',halign='left',valign='top',size_hint_y=None,font_size=dp(14)); self.out.bind(texture_size=lambda inst,val:setattr(inst,'height',max(val[1],dp(500)))); scroll.add_widget(self.out); root.add_widget(scroll)
        Clock.schedule_once(lambda dt:self.auto_sync(),0.5); Clock.schedule_interval(lambda dt:self.auto_sync(),21600); return root

    def status(self,text): self.out.text=text
    def auto_sync(self):
        if getattr(self,'_sync_running',False): return
        self._sync_running=True; self.update_btn.disabled=True; self.progress.value=0.05; self.status('Sincronização automática...\nVerificando novo concurso na Caixa...')
        threading.Thread(target=self.worker,args=(int(self.conc.text),int(self.ng.text)),daemon=True).start()
    def run_analysis(self,*_): self.auto_sync()
    def run_saved(self,*_):
        try:
            hist=load_history()
            if not hist: raise RuntimeError('Não há dados salvos. Atualize primeiro.')
            self.show_results(hist,int(self.ng.text),updated=False)
        except Exception as e: self.status('Erro: '+str(e))
    def worker(self,n,ng):
        try:
            hist,changed,latest_no=sync_history(n); model=load_model()
            if changed or model is None or int(model.get('trained_on',0))!=len(hist): model=fit_adaptive_model(hist); save_model(model)
            Clock.schedule_once(lambda dt:self.show_results(hist,ng,updated=changed,latest_no=latest_no),0)
        except Exception as e: Clock.schedule_once(lambda dt:self.status('Erro na atualização automática: '+str(e)),0)
        finally: Clock.schedule_once(lambda dt:self.finish_sync(),0)
    def finish_sync(self): self._sync_running=False; self.update_btn.disabled=False
    def show_results(self,hist,ng,updated=False,latest_no=None):
        self.progress.value=1; model=load_model() or fit_adaptive_model(hist); ranking=adaptive_probabilities(hist,model); games=generate_games(ranking,ng)
        top='\n'.join(f"{i+1:02d}. {r['numero']:02d} | score {r['score']:6.2f} | modelo {r['model_prob']:.5f}" for i,r in enumerate(ranking[:20]))
        gs='\n'.join(f"{i+1:02d}. {' '.join(f'{x:02d}' for x in g)} | score {s:.2f} | soma {total} | pares {ev}" for i,(s,g,total,ev) in enumerate(games))
        latest=hist[-1]; state='NOVO CONCURSO INCORPORADO' if updated else 'Dados já estavam atualizados'
        self.status(f"{state}\nConcursos no modelo: {len(hist)}\nÚltimo concurso: {latest['concurso']} ({latest['data']})\n\nTOP 20 DEZENAS — MODELO ADAPTATIVO\n{top}\n\nJOGOS RANQUEADOS\n{gs}\n\nAPRENDIZADO AUTOMÁTICO\nModelo treinado com {model.get('trained_on',len(hist))} concursos.\nÚltimo treinamento: {model.get('trained_at','agora')}\nA sincronização verifica novos concursos ao abrir o app e a cada 6 horas enquanto ele estiver aberto.\n\nIMPORTANTE: em um sorteio justo, todas as dezenas continuam tendo a mesma probabilidade matemática. O modelo apenas aprende padrões históricos e produz um ranking experimental; ele não cria uma probabilidade real maior para uma dezena e não garante acertos.")


if __name__=='__main__': MegaSenaApp().run()
