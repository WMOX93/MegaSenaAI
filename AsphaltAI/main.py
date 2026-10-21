import json, os
from datetime import datetime
from kivy.app import App
from kivy.clock import Clock
from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

DATA='events.json'

def load_events():
    if not os.path.exists(DATA): return []
    with open(DATA,encoding='utf-8') as f: return json.load(f)

def parse_dt(s):
    try: return datetime.fromisoformat(s)
    except: return datetime.now().astimezone()

def fmt(sec):
    sec=max(0,int(sec)); d,sec=divmod(sec,86400); h,sec=divmod(sec,3600); m=sec//60
    return f'{d}d {h:02d}h {m:02d}m' if d else f'{h:02d}h {m:02d}m'

def priority(e):
    now=datetime.now().astimezone(); remaining=(parse_dt(e['deadline'])-now).total_seconds()
    left=max(0,int(e['target'])-int(e['progress'])); est=left*max(1,int(e.get('avg_race_seconds',240)))
    if left==0: level='COMPLETA'
    elif remaining<=0: level='EXPIRADO'
    elif remaining-est<0: level='EMERGÊNCIA'
    elif remaining<=3600: level='CRÍTICA'
    elif remaining<=10800: level='URGENTE'
    elif remaining<=43200: level='ALTA'
    elif remaining<=86400: level='MÉDIA'
    else: level='NORMAL'
    risk=1000 if level=='EXPIRADO' else max(0,900-int(max(0,remaining-est)/max(remaining,1)*900))
    return risk,level,remaining,est

class AsphaltAI(App):
    def build(self):
        self.title='Asphalt AI Bot'
        root=BoxLayout(orientation='vertical',padding=dp(10),spacing=dp(8))
        root.add_widget(Label(text='[b]ASPHALT AI BOT[/b]',markup=True,font_size=dp(24),size_hint_y=None,height=dp(50)))
        self.status=Label(size_hint_y=None,height=dp(35)); root.add_widget(self.status)
        b=BoxLayout(size_hint_y=None,height=dp(50),spacing=dp(6))
        x=Button(text='ATUALIZAR PRAZOS'); x.bind(on_release=lambda *_: self.refresh()); b.add_widget(x)
        y=Button(text='MODO DEADLINE'); y.bind(on_release=lambda *_: self.deadline()); b.add_widget(y); root.add_widget(b)
        self.scroll=ScrollView(); self.list=BoxLayout(orientation='vertical',spacing=dp(8),size_hint_y=None); self.list.bind(minimum_height=self.list.setter('height')); self.scroll.add_widget(self.list); root.add_widget(self.scroll)
        Clock.schedule_interval(lambda dt:self.refresh(),1); self.refresh(); return root
    def refresh(self):
        self.list.clear_widgets(); events=sorted(load_events(),key=lambda e:priority(e)[0],reverse=True); urgent=0
        for e in events:
            score,level,rem,est=priority(e); left=max(0,e['target']-e['progress']); urgent += level in ('EMERGÊNCIA','CRÍTICA','URGENTE')
            txt=f'[b]{level} — {e["name"]}[/b]\nMissão: {e["mission"]}\nProgresso: {e["progress"]}/{e["target"]}\nPrazo: {fmt(rem)} | Estimativa: {fmt(est)}\n' + ('EXECUTAR AGORA' if rem-est<0 and left else 'Prioridade recalculada automaticamente')
            self.list.add_widget(Label(text=txt,markup=True,size_hint_y=None,height=dp(120)))
        self.status.text=f'{len(events)} eventos • {urgent} urgentes • atualização contínua'
    def deadline(self):
        ev=sorted(load_events(),key=lambda e:priority(e)[0],reverse=True)
        self.status.text='DEADLINE: '+(ev[0]['name'] if ev else 'nenhum evento')
        self.refresh()

if __name__=='__main__': AsphaltAI().run()
