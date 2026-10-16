# MeuSaldo — gestão financeira

Aplicativo responsivo de gestão financeira feito com Python, Streamlit e Cloud
Firestore. Cada pessoa cria uma conta e visualiza somente os próprios
lançamentos. As senhas são armazenadas no Firestore como hashes PBKDF2-SHA256
com salt aleatório; elas nunca são gravadas em texto puro. O cadastro e o login
são gerenciados pelo próprio app no Firestore (não pelo Firebase Authentication),
portanto não é necessária uma chave de API web do Firebase.

## Executar localmente

1. Use Python 3.10 ou superior.
2. Instale as dependências:

   ```powershell
   py -m pip install -r requirements.txt
   ```

3. Para desenvolvimento local, mantenha o arquivo de credenciais do Firebase
   ao lado de `app.py` ou preencha `.streamlit/secrets.toml`. Esse arquivo é
   ignorado pelo Git.
4. No console Firebase do projeto `app-gestao-finaceira`, habilite o Cloud
   Firestore e confirme que o banco `default` está criado.
5. Inicie o aplicativo:

   ```powershell
   py -m streamlit run app.py
   ```

Se o arquivo de credenciais estiver em outro local, defina a variável
`FIREBASE_CREDENTIALS_PATH` com o caminho completo antes de iniciar o app.

## Publicar no Streamlit Community Cloud

1. Envie o código para o GitHub sem o JSON de credenciais ou
   `.streamlit/secrets.toml`.
2. No [share.streamlit.io](https://share.streamlit.io), crie o app escolhendo
   o repositório e `app.py`.
3. Abra as configurações avançadas do deploy e cole o conteúdo preenchido de
   `.streamlit/secrets.toml` no campo **Secrets**. Nunca publique a chave no
   repositório.

Na tela inicial, é possível escolher uma foto de perfil (visível durante a
sessão) e acompanhar o gráfico circular das despesas por categoria. Ao registrar
uma despesa, selecione uma categoria; lançamentos antigos sem categoria são
exibidos como “Outros”. O gráfico fica à esquerda, com valores e percentuais
das categorias logo abaixo. No formulário, a descrição oferece opções comuns
para receitas e despesas, além de permitir digitar uma descrição personalizada.

## Dados no Firestore

- `users/{usuario}`: nome de usuário, salt e hash da senha.
- `transactions/{id}`: usuário proprietário, tipo, categoria (para despesas),
  descrição, valor e data.

Não publique nem envie o JSON da conta de serviço para o repositório ou para o
navegador. Em hospedagem, armazene-o como segredo e disponibilize-o ao processo
do Streamlit por um arquivo protegido; configure `FIREBASE_CREDENTIALS_PATH`
para apontar para esse arquivo. As regras do Firestore não substituem a
autorização feita pelo servidor: a conta de serviço tem acesso administrativo.
