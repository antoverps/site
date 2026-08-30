# Site Prof. Antover — Hugo Profile v1

Base: Hugo Profile v4.06  
Publicação: GitHub Pages  
URL prevista: https://antoverps.github.io/site/

## O que já está configurado

- identidade verde institucional;
- seletor claro/escuro do Hugo Profile;
- português como idioma principal;
- estrutura pronta para habilitar inglês depois da tradução;
- Sobre com o texto do Google Sites atual;
- Atuação em 3 frentes;
- Formação;
- 13 projetos, incluindo o acervo histórico do Google Sites;
- Resultados/infraestrutura;
- Atualizações usando `content/blogs/`;
- contato institucional;
- GitHub Pages via GitHub Actions;
- Hugo Profile v4.06 baixado automaticamente durante o build.

## Antes de subir este pacote no repositório

No repositório `antoverps/site`, remova o arquivo antigo:

- `config.toml`

Se existirem arquivos da tentativa estática anterior, remova também:

- `index.html`
- `.nojekyll`

O arquivo `content/_index.md` deste pacote deve substituir o antigo.

## Como publicar

1. Extraia este ZIP.
2. No GitHub, abra `antoverps/site`.
3. Envie todos os arquivos e pastas desta estrutura para a raiz do repositório.
4. Faça commit na `main`.
5. Abra **Settings > Pages**.
6. Em **Build and deployment > Source**, escolha **GitHub Actions**.
7. Abra a aba **Actions** e acompanhe `Deploy Hugo Profile to GitHub Pages`.
8. Ao finalizar, abra:
   https://antoverps.github.io/site/

## Observação sobre imagens

Os links das imagens históricas foram recuperados do Google Sites e preservados na configuração/Planilha-Mãe.
O servidor `googleusercontent` bloqueou a cópia direta durante a migração. Se algum link não renderizar no GitHub Pages,
substituiremos o URL por uma imagem local em `static/images/`.

## Inglês

A estrutura `content/en/` e um bloco comentado no `hugo.yaml` foram deixados prontos.
O inglês não foi ativado nesta versão para evitar um seletor EN exibindo conteúdo ainda não traduzido.

## Próximo passo

Depois que esta primeira versão estiver publicada:
1. conferir visual;
2. ajustar o segundo botão do hero para `Entrar em contato`;
3. revisar textos curtos dos projetos;
4. substituir imagens instáveis por arquivos locais;
5. conectar a aba `07 - Atualizações Hugo` da Planilha-Mãe aos posts.
