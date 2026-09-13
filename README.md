# Leilões da Caixa · São Paulo

Mapa dos imóveis em leilão da Caixa no estado de São Paulo, com comparação
entre regiões e o custo real de arremate. Atualiza sozinho toda segunda-feira
e fica acessível de qualquer navegador, inclusive celular.

---

## Como colocar no ar

Você faz isso uma vez. Leva uns 10 minutos.

### 1. Criar o repositório

1. Entre em <https://github.com> e crie uma conta, se ainda não tiver.
2. Clique em **New repository**.
3. Dê um nome (por exemplo `leiloes-caixa-sp`), marque **Public** e crie.
4. Na tela seguinte, clique em **uploading an existing file** e arraste
   *todos* os arquivos desta pasta, inclusive a pasta `.github`.

> Se o navegador não deixar arrastar a pasta `.github`, crie o arquivo pela
> web: **Add file → Create new file**, e no nome digite
> `.github/workflows/atualizar.yml` — o GitHub cria as pastas sozinho.
> Cole dentro o conteúdo do arquivo correspondente.

### 2. Ligar a publicação

1. No repositório, vá em **Settings → Pages**.
2. Em **Source**, escolha **GitHub Actions**.

### 3. Ligar a permissão de escrita

1. **Settings → Actions → General**.
2. Em **Workflow permissions**, marque **Read and write permissions** e salve.
   Sem isso o robô não consegue guardar o banco atualizado.

### 4. Rodar pela primeira vez

1. Vá na aba **Actions**.
2. Clique em **Atualizar mapa de leilões** e depois em **Run workflow**.
3. Espere. Quando terminar, o endereço do site aparece em **Settings → Pages**.
   Costuma ser `https://SEU-USUARIO.github.io/leiloes-caixa-sp/`.

Guarde esse endereço nos favoritos do celular. É só isso que você vai usar.

---

## A chave de mapa (opcional, mas recomendada)

Sem chave, o robô usa o serviço gratuito do OpenStreetMap. Funciona, mas a
[política de uso do Nominatim](https://operations.osmfoundation.org/policies/nominatim/)
restringe scripts que rodam em intervalos regulares a **4 consultas por
minuto**. O robô respeita isso, então uma semana com 300 endereços novos leva
cerca de 75 minutos. Vale ler a política antes de decidir: ela também exige
que os resultados fiquem em cache do seu lado e proíbe rodar de várias
máquinas ao mesmo tempo.

Com uma chave da HERE, a mesma tarefa leva menos de 2 minutos.

1. Crie a conta gratuita (sem cartão) em <https://platform.here.com/>.
2. Crie um projeto e gere uma **API Key** para *Geocoding & Search*.
3. No GitHub: **Settings → Secrets and variables → Actions → New repository secret**.
4. Nome: `HERE_API_KEY`. Valor: a chave. Salve.

O robô detecta a chave sozinho e passa a usá-la. Sem a chave, ele continua
funcionando pelo caminho gratuito — nada quebra.

> **Nunca coloque a chave dentro de um arquivo do repositório.** Ele é público.
> Secret é o lugar certo: fica cifrado e não aparece para ninguém.

---

## Quanto isso custa

Nada, na prática.

| Item | Situação |
|---|---|
| GitHub Actions em repositório público | gratuito e sem limite de minutos |
| GitHub Pages | gratuito |
| HERE, plano Limited | 1.000 consultas por dia, sem cartão |
| Consumo real do robô | cerca de 300 consultas por semana |

---

## Por que o cache vence em 30 dias

O arquivo `geocodificar.py` apaga do cache qualquer coordenada com mais de 30
dias e consulta de novo. Isso não é capricho técnico: HERE e Google limitam a
30 dias o tempo que você pode guardar uma coordenada obtida com eles.

E aqui isso quase não custa nada, porque a lista da Caixa se renova mais
rápido que o cache: entre 8 de agosto e 11 de setembro de 2026, **83% da lista
de São Paulo mudou**. Uma coordenada de 30 dias atrás geralmente é de um
imóvel que já foi vendido.

Se algum dia você quiser desligar a validade, mude `CACHE_DIAS` para `0` no
arquivo do robô — mas confira antes os termos do provedor que estiver usando.

---

## Se algo der errado

| Sintoma | O que fazer |
|---|---|
| O robô falha em "Baixar a lista" | O site da Caixa bloqueou o acesso. Rode de novo mais tarde pelo **Run workflow**. O mapa antigo continua no ar. |
| Falha em "Guardar o banco" | Falta a permissão de escrita. Veja o passo 3. |
| O site não aparece | Confirme que **Settings → Pages** está em **GitHub Actions**. |
| A localização está lenta demais | Cadastre a chave da HERE. |

Cada execução fica registrada na aba **Actions**, com o log completo.

---

## O que é cada arquivo

| Arquivo | Função |
|---|---|
| `.github/workflows/atualizar.yml` | O robô: quando roda e o que faz |
| `baixar_caixa.py` | Baixa e limpa a lista da Caixa |
| `endereco.py` | Separa logradouro, número e complemento |
| `geocodificar.py` | Descobre as coordenadas |
| `regioes.py` | Classifica por região metropolitana e distrito |
| `custos.py` | Calcula custo total e preço de equilíbrio |
| `gerar_mapa.py` | Monta a página final |
| `imoveis_caixa.db` | O banco, com o cache de coordenadas |
| `site/index.html` | O mapa publicado |

---

## Uma ressalva sobre os números

O desconto é calculado sobre o **valor de avaliação da Caixa**, que não é
preço de mercado. Use o **preço de equilíbrio em R$/m²** de cada região e
compare com o que você sabe que se pede ali. Nenhum número aqui substitui
ler o edital e visitar o imóvel.
