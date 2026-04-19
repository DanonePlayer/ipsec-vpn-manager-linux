# IPsec VPN Manager for Linux

Aplicativo gráfico (GUI) para gerenciar conexões VPN IPsec/XAuth com strongSwan no Linux. Interface simples para conectar, desconectar e gerenciar perfis VPN sem precisar editar arquivos de configuração manualmente.

## Funcionalidades

- Interface gráfica com tema escuro
- Gerenciamento de múltiplos perfis VPN
- Conexão/desconexão com um clique
- Resolução automática de IP do servidor
- Configuração automática de DNS ao conectar
- Restauração de DNS ao desconectar
- Log de conexão em tempo real
- Autenticação sudo via janela gráfica (sem uso do terminal)

## Requisitos

### Sistema operacional
- Linux (testado no Pop!\_OS / Ubuntu)

### Dependências

```bash
sudo apt install strongswan python3 python3-tk
```

## Instalação e configuração

### 1. Clone o repositório

```bash
git clone https://github.com/SEU_USUARIO/ipsec-vpn-manager-linux.git
cd ipsec-vpn-manager-linux
```

### 2. Configure o perfil VPN

Copie o arquivo de exemplo e edite com seus dados:

```bash
cp config.example.json config.json
```

Edite o `config.json`:

```json
{
    "profiles": [
        {
            "name": "NOME_DA_CONEXAO",
            "server": "vpn.suaempresa.com.br",
            "username": "seu.usuario",
            "password": "sua_senha_xauth",
            "preshared_key": "sua_chave_psk"
        }
    ]
}
```

| Campo | Descrição |
|-------|-----------|
| `name` | Nome da conexão (sem espaços) |
| `server` | Endereço do servidor VPN |
| `username` | Usuário XAuth |
| `password` | Senha XAuth |
| `preshared_key` | Chave pré-compartilhada (PSK) |

### 3. Execute o app

```bash
python3 vpn-manager.py
```

## Como usar

1. Abra o app
2. Selecione o perfil desejado na lista
3. Preencha **usuário** e **senha** nos campos
4. Clique em **Conectar**
5. Na primeira vez, será solicitada a senha do sistema (sudo) via janela gráfica
6. Acompanhe o log de conexão na parte inferior

Para desconectar, clique em **Desconectar**.

## Como o app funciona

Ao conectar, o app:

1. Resolve o IP do servidor VPN
2. Grava `/etc/ipsec.secrets` com PSK e credenciais XAuth
3. Grava `/etc/ipsec.conf` com os parâmetros da conexão
4. Recarrega o strongSwan (`ipsec rereadall` + `ipsec reload`)
5. Executa `ipsec up <conexao>`
6. Define o DNS recebido pelo servidor VPN em `/etc/resolv.conf`

Ao desconectar:

1. Executa `ipsec down <conexao>`
2. Restaura DNS para `8.8.8.8` em `/etc/resolv.conf`

## Estrutura do projeto

```
ipsec-vpn-manager-linux/
├── vpn-manager.py        # Aplicativo principal
├── config.json           # Seus perfis VPN (não commitado)
├── config.example.json   # Exemplo de configuração
└── .gitignore
```

## Observações

- O app requer permissão `sudo` para editar arquivos de sistema (`/etc/ipsec.conf`, `/etc/ipsec.secrets`, `/etc/resolv.conf`) e controlar o strongSwan
- O `config.json` contém credenciais sensíveis — **não suba para repositórios públicos**
- Testado com strongSwan 5.9.x em conexões IKEv1/XAuth PSK
