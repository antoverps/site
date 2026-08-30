# Site Prof. Antover — Hugo Profile v2

## Alterações desta versão

- hero com título e tagline menores;
- Formação removida da Home e do menu;
- "Atuação" renomeada para **Atuação e áreas de interesse**;
- projetos migrados para `content/projects/`;
- a Home exibe apenas projetos com `showInHome: true`;
- o menu **Projetos** abre o acervo completo em `/projects/`;
- botão **Ver todos os projetos →** é inserido abaixo dos projetos ativos;
- seção **Resultados** renomeada para **Grupos e Infraestrutura**;
- apenas 3 Atualizações recentes na Home;
- rodapé com ResearchGate, Lattes, ORCID, GitHub e Instagram;
- crédito do tema mantido em formato profissional:
  **Tecnologia: Hugo · Tema-base: Hugo Profile**.

## Regra de projetos

A arquitetura já está preparada para automação com a Planilha-Mãe:

- `Publicar = SIM` → projeto permanece no acervo;
- `Status = Ativo` + `Destaque Home = SIM` + `Publicar = SIM` → aparece na Home;
- projetos concluídos continuam no acervo completo, mas não ocupam a Home.

Nesta versão, somente o **PDDU Catalão** está marcado como ativo na base atualmente conhecida.

## Publicação

Substitua no repositório os arquivos equivalentes por esta versão e faça commit na `main`.
O workflow existente continuará publicando com Hugo Profile v4.06 via GitHub Actions.
