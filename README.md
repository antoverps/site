# Meu Site - Hugo Blox

Site pessoal criado com [Hugo](https://gohugo.io/) e o template [Hugo Blox](https://hugoblox.com/).

## 🚀 Início Rápido

### Pré-requisitos
- Hugo Extended (v0.120+)
- Git

### Clone e Setup

```bash
# Clone o repositório com o submodule do tema
git clone --recurse-submodules https://github.com/antoverps/site.git
cd site

# Se já clonou sem submodule, execute:
git submodule update --init --recursive
```

### Desenvolvimento Local

```bash
# Inicie o servidor de desenvolvimento
hugo server

# Acesse em http://localhost:1313
```

### Build

```bash
# Gere os arquivos estáticos
hugo

# Os arquivos estarão em ./public/
```

## 📝 Estrutura

```
site/
├── config.toml          # Configurações do site
├── content/             # Conteúdo (páginas, posts)
├── themes/hugo-blox/    # Tema Hugo Blox
└── static/              # Arquivos estáticos
```

## 🌐 Deploy

O site será publicado em `https://antoverps.github.io/site/` quando você fizer push para a branch `main`.

## 📚 Documentação

- [Hugo Docs](https://gohugo.io/documentation/)
- [Hugo Blox Docs](https://hugoblox.com/docs/)

## 📄 Licença

MIT
