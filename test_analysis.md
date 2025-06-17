# Análise do Script `stress_test_scraper.py`

Este script é um teste de estresse avançado para um scraper web (MarketRoxoScraperCloudflare) que inclui estratégias sofisticadas para lidar com falhas e contornar proteções como o Cloudflare. Vamos descrevê-lo passo a passo:

## 1. Configuração Inicial
- Importa bibliotecas necessárias (json, os, time, random, threading, etc.)
- Define configuração de logs (ENABLE_SCRAPER_LOGS) que pode ativar/desativar logs internos do scraper
- Cria funções de callback para logging (scraper_internal_log_callback e main_script_log)

## 2. Funções Auxiliares
- `_mutate_keywords`: Modifica palavras-chave aleatoriamente (substitui caracteres) para testar resiliência
- `_remove_random_keyword`: Remove palavras-chave aleatoriamente mantendo um mínimo
- `ProgressUpdater`: Classe para gerenciar barras de progresso em threads

## 3. Função Principal de Teste (`run_until_failure_test`)
Executa testes de scraping com estratégias de retry avançadas:

### Estratégias de Retry (Fases):
1. **Fase 0 (Tentativas 1-10)**: Testa sem modificações (no_shuffle)
2. **Fase 1 (Tentativas 1-10 após falha)**: Apenas embaralha palavras-chave (shuffle_only)
3. **Fase 2 (Tentativas 11-25)**: Embaralha + 1 mutação leve
4. **Fase 3 (Tentativas 26-50)**: Embaralha + 2 mutações
5. **Fase 4 (Tentativas 51-75)**: Embaralha + 3 mutações
6. **Fase 5 (Tentativas 76+)**: Embaralha + mutações progressivas

### Condições de Parada:
- Atingir número máximo de chamadas (`max_total_calls`)
- Obter 5 sucessos consecutivos (`SUCCESS_STREAK_THRESHOLD`)

### Métricas Coletadas:
- Contagem de sucessos/falhas
- Estratégias mais bem-sucedidas
- Palavras-chave usadas
- Erros encontrados

## 4. Função `main()`
Configura e executa os testes:

1. **Configuração**:
   - Carrega variáveis de ambiente (.env)
   - Define URLs, proxies, palavras-chave padrão e negativas
   - Cria instância do scraper

2. **Casos de Teste**:
   - Define diferentes conjuntos de palavras-chave para testar
   - (Atualmente apenas um teste ativo com palavras-chave padrão)

3. **Execução Paralela**:
   - Usa ThreadPoolExecutor para rodar testes em paralelo
   - Monitora progresso com barra de progresso (Rich)
   - Coleta resultados detalhados

4. **Saída**:
   - Exibe resumo dos resultados no console
   - Salva resultados detalhados em JSON (`stress_test_results.json`)

## 5. Objetivo Principal
O script testa a resiliência do scraper contra:
- Bloqueios do Cloudflare
- Variações nas palavras-chave
- Falhas temporárias
- Limites de requisições

Através de estratégias progressivas que modificam os parâmetros de busca quando encontram falhas.

## Fluxo Detalhado:
1. Inicia com palavras-chave originais
2. Se falhar, tenta estratégias cada vez mais agressivas:
   - Embaralhar palavras-chave
   - Modificar caracteres nas palavras
   - Remover palavras-chave
3. Registra qual estratégia teve mais sucesso
4. Para após sucesso consistente ou muitas tentativas
5. Gera relatório detalhado do teste

Este script é particularmente útil para validar a robustez de um scraper em ambientes hostis com proteções anti-bot.