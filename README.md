# Mega-Sena AI V3.1 — Android

Aplicativo Kivy/Buildozer para Android com atualização incremental dos concursos da Mega-Sena e modelo adaptativo experimental.

## Recursos
- Consulta dos resultados da Caixa.
- Histórico local.
- Sincronização incremental de novos concursos.
- Reprocessamento do modelo quando um novo concurso é incorporado.
- Ranking experimental das 60 dezenas.
- Geração de jogos ranqueados.
- APK compilado automaticamente pelo GitHub Actions.

## APK
O workflow `Build Android APK` é executado a cada push na `main` ou manualmente em **Actions → Build Android APK → Run workflow**. O APK é publicado no artefato `MegaSenaAI-APK`.

## Observação estatística
O ranking é experimental e usa características históricas. Em uma loteria justa, o histórico não altera a probabilidade matemática real de cada combinação futura.
