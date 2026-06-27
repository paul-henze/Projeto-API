## Projeto Multidisciplinar - Raízes do Nordeste — API REST ##

API REST para gerenciamento de pedidos multicanal da rede de lanchonetes **Raízes do Nordeste**.

RU:4738874 

Aluno: Paul Stanley Henze

## Sobre o Projeto ##

O projeto Raízes do Nordeste é uma API REST desenvolvida em Python com o FastAPI, SQLAlchemy e SQLite.

Criada para gerenciar pedidos Multicanal de uma rede de lanchonetes chamada "Raízes do Nordeste".

Ele organiza fluxos de pedidos, pagamentos, fidelidade e controle de estoque, com autenticação via

JWT e diferentes níveis de acesso (roles).

## Requisitos Necessários ##

* Python 3.12
* pip

## Clone ou baixe os arquivos do repositório e Instale as dependências ##

* comando: pip install -r requirements.txt

## Execute o servidor ##

* Comando: uvicorn app.main:app --reload


## Endereços ##

Endereço de acesso para a API http://127.0.0.1:8000

Endereço de acesso para Documentação Swagger: http://127.0.0.1:8000/docs#/

## Login e Autenticação ##

* Crie um usuário utilizando o `POST /usuarios`
* Faça login com `POST /auth/login` e copie o `accessToken`
* No Swagger, clique em `Authorize` e cole: `Bearer <token>`

## Fluxo principal ##
```
                     -                    Ação                      -            Permissões 
POST /usuarios                Realiza a criação de usuário (público)
POST /auth/login              obtém o token JWT (público)
POST /unidades                Realiza o cadastro da unidade                   GERENTE ou ADMIN
POST /produtos                Realiza o cadastro de produto                   GERENTE ou ADMIN
POST /estoque                 realiza controle de estoque                     GERENTE ou ADMIN
POST /pedidos                 realiza a criação do pedido                 Qualquer nível de usuário
POST /pagamentos/processar    processa o pagamento                        Qualquer nível de usuário
GET  /fidelidade/saldo        Consulta saldo de pontos                  Usuário com Consentimento LGPD
```

---

## Canais de pedido válidos ##

APP, BALCAO, PICKUP, TOTEM, WEB


## Roles

| Role          | Permissões                                              |
|---------------|---------------------------------------------------------|
| `CLIENTE`     | Criar e ver apenas os próprios pedidos, pagar, fidelidade |
| `ATENDENTE`   | Ver todos os pedidos                                    |
| `COZINHA`     | Ver todos os pedidos                                    |
| `GERENTE`     | Todas as anteriores + gerenciar unidades, produtos e estoque |
| `ADMIN`       | Acesso total                                            |


## Status do pedido ##

* AGUARDANDO PAGAMENTO
* RECEBIDO
* EM PREPARACAO
* PRONTO
* PEDIDO ENTREGUE
* (Ou CANCELADO)
