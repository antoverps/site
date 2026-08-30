# Automação Planilha-Mãe → Atualizações

A estrutura do site já usa `content/blogs/` para alimentar **Atualizações / Recent Posts**.

Próxima etapa:
1. Publicar a aba `07 - Atualizações Hugo` do Google Sheets como CSV.
2. Informar a URL CSV.
3. Criar um script que transforme as linhas com `Publicar? = SIM` em arquivos Markdown.
4. Rodar o script no GitHub Actions antes do comando `hugo`.

A automação ainda NÃO está ativada nesta versão para evitar publicação acidental de rascunhos ou linhas de exemplo.
