import tkinter as tk
from tkinter import messagebox
import subprocess
import threading
import json
import socket
import os
import time
import tempfile
import atexit
import signal

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")
_senha_sudo = None


def restaurar_dns():
    try:
        inp = (_senha_sudo + "\n").encode() if _senha_sudo else b""
        subprocess.run(
            ["sudo", "-S", "bash", "-c", "echo 'nameserver 8.8.8.8' > /etc/resolv.conf"],
            input=inp, capture_output=True, timeout=5
        )
    except Exception:
        pass


atexit.register(restaurar_dns)
signal.signal(signal.SIGTERM, lambda s, f: (restaurar_dns(), exit(0)))
signal.signal(signal.SIGINT, lambda s, f: (restaurar_dns(), exit(0)))


def load_config():
    with open(CONFIG_FILE, "r") as f:
        return json.load(f)


def save_config(config):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=4)


def resolve_ip(domain):
    try:
        return socket.gethostbyname(domain)
    except Exception:
        return None


def sudo_run(args, senha, timeout=30):
    try:
        result = subprocess.run(
            ["sudo", "-S"] + args,
            input=(senha + "\n").encode(),
            capture_output=True, timeout=timeout
        )
        return result.stdout.decode("utf-8", errors="replace") + result.stderr.decode("utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return "Erro: timeout na operação\n"


def write_as_root(path, content, senha):
    tmp = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.tmp', delete=False) as f:
            f.write(content)
            tmp = f.name
        result = subprocess.run(
            ["sudo", "-S", "cp", tmp, path],
            input=(senha + "\n").encode(),
            capture_output=True, timeout=10
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        if tmp and os.path.exists(tmp):
            os.unlink(tmp)


def get_status(senha=""):
    output = sudo_run(["ipsec", "statusall"], senha, timeout=10)
    return "conectado" if "ESTABLISHED" in output.upper() else "desconectado"


class SenhaDialog(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Autenticação do sistema")
        self.configure(bg="#1e1e2e")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        tk.Label(self, text="Senha do sistema (sudo):", bg="#1e1e2e", fg="#aaa",
                 font=("Arial", 10)).pack(padx=20, pady=(20, 5))
        self.entry = tk.Entry(self, show="●", font=("Arial", 11), bg="#2e2e3e",
                              fg="white", insertbackground="white", relief=tk.FLAT, width=25)
        self.entry.pack(padx=20, pady=5)
        self.entry.bind("<Return>", lambda e: self._confirmar())

        frame = tk.Frame(self, bg="#1e1e2e")
        frame.pack(pady=15)
        tk.Button(frame, text="Confirmar", width=10, bg="#4CAF50", fg="white",
                  relief=tk.FLAT, cursor="hand2", font=("Arial", 10, "bold"),
                  command=self._confirmar).pack(side=tk.LEFT, padx=8)
        tk.Button(frame, text="Cancelar", width=10, bg="#555", fg="white",
                  relief=tk.FLAT, cursor="hand2", font=("Arial", 10),
                  command=self.destroy).pack(side=tk.LEFT, padx=8)

        self.entry.focus()

    def _confirmar(self):
        self.result = self.entry.get()
        self.destroy()


class ProfileDialog(tk.Toplevel):
    def __init__(self, parent, profile=None):
        super().__init__(parent)
        self.title("Editar Perfil" if profile else "Novo Perfil")
        self.configure(bg="#1e1e2e")
        self.resizable(False, False)
        self.grab_set()
        self.result = None

        fields = [
            ("Nome:", "name", False),
            ("Servidor:", "server", False),
            ("Usuário:", "username", False),
            ("Senha:", "password", True),
            ("Chave Pré-compartilhada:", "preshared_key", True),
        ]

        self.entries = {}
        for i, (label, key, is_pass) in enumerate(fields):
            tk.Label(self, text=label, bg="#1e1e2e", fg="#aaa",
                     font=("Arial", 10)).grid(row=i, column=0, sticky="w", padx=15, pady=6)
            entry = tk.Entry(self, font=("Arial", 11), bg="#2e2e3e", fg="white",
                             insertbackground="white", relief=tk.FLAT, width=25,
                             show="●" if is_pass else "")
            entry.grid(row=i, column=1, padx=10, pady=6)
            if profile:
                entry.insert(0, profile.get(key, ""))
            self.entries[key] = entry

        frame_btns = tk.Frame(self, bg="#1e1e2e")
        frame_btns.grid(row=len(fields), column=0, columnspan=2, pady=15)
        tk.Button(frame_btns, text="Salvar", width=10, bg="#4CAF50", fg="white",
                  relief=tk.FLAT, cursor="hand2", font=("Arial", 10, "bold"),
                  command=self.save).pack(side=tk.LEFT, padx=8)
        tk.Button(frame_btns, text="Cancelar", width=10, bg="#555", fg="white",
                  relief=tk.FLAT, cursor="hand2", font=("Arial", 10),
                  command=self.destroy).pack(side=tk.LEFT, padx=8)

    def save(self):
        self.result = {key: entry.get().strip() for key, entry in self.entries.items()}
        if not all(self.result.values()):
            messagebox.showerror("Erro", "Preencha todos os campos!", parent=self)
            return
        self.destroy()


class VPNManager(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("VPN Manager")
        self.geometry("520x520")
        self.configure(bg="#1e1e2e")
        self.resizable(False, False)
        self.config_data = load_config()
        self.selected_profile = None
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.build_ui()
        self.refresh_list()
        self.update_status()

    def _log(self, text):
        self.after(0, lambda t=text: (
            self.log_text.insert(tk.END, t),
            self.log_text.see(tk.END)
        ))

    def _obter_senha_sudo(self):
        global _senha_sudo
        if _senha_sudo:
            return _senha_sudo
        dialog = SenhaDialog(self)
        self.wait_window(dialog)
        if not dialog.result:
            return None
        _senha_sudo = dialog.result
        return _senha_sudo

    def build_ui(self):
        tk.Label(self, text="VPN Manager", font=("Arial", 18, "bold"),
                 bg="#1e1e2e", fg="white").pack(pady=(20, 5))

        frame_status = tk.Frame(self, bg="#1e1e2e")
        frame_status.pack()
        self.status_dot = tk.Label(frame_status, text="●", font=("Arial", 14),
                                   bg="#1e1e2e", fg="gray")
        self.status_dot.pack(side=tk.LEFT)
        self.status_label = tk.Label(frame_status, text="Verificando...",
                                     font=("Arial", 12), bg="#1e1e2e", fg="gray")
        self.status_label.pack(side=tk.LEFT, padx=5)

        tk.Label(self, text="Perfis:", bg="#1e1e2e", fg="#aaa",
                 font=("Arial", 10)).pack(anchor="w", padx=20, pady=(15, 3))

        frame_list = tk.Frame(self, bg="#1e1e2e")
        frame_list.pack(padx=20, fill=tk.X)
        self.listbox = tk.Listbox(frame_list, bg="#2e2e3e", fg="white",
                                  font=("Arial", 11), relief=tk.FLAT,
                                  selectbackground="#4CAF50", height=5,
                                  activestyle="none")
        self.listbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.listbox.bind("<<ListboxSelect>>", self.on_select)

        frame_manage = tk.Frame(self, bg="#1e1e2e")
        frame_manage.pack(pady=8)
        tk.Button(frame_manage, text="+ Novo", width=8, bg="#2e2e3e", fg="white",
                  relief=tk.FLAT, cursor="hand2", font=("Arial", 9),
                  command=self.new_profile).pack(side=tk.LEFT, padx=4)
        tk.Button(frame_manage, text="✎ Editar", width=8, bg="#2e2e3e", fg="white",
                  relief=tk.FLAT, cursor="hand2", font=("Arial", 9),
                  command=self.edit_profile).pack(side=tk.LEFT, padx=4)
        tk.Button(frame_manage, text="✕ Excluir", width=8, bg="#2e2e3e", fg="white",
                  relief=tk.FLAT, cursor="hand2", font=("Arial", 9),
                  command=self.delete_profile).pack(side=tk.LEFT, padx=4)

        frame_inputs = tk.Frame(self, bg="#1e1e2e")
        frame_inputs.pack(pady=5, padx=20, fill=tk.X)
        tk.Label(frame_inputs, text="Usuário:", bg="#1e1e2e", fg="#aaa",
                 font=("Arial", 10)).grid(row=0, column=0, sticky="w", pady=4)
        self.entry_user = tk.Entry(frame_inputs, font=("Arial", 11), bg="#2e2e3e",
                                   fg="white", insertbackground="white",
                                   relief=tk.FLAT, width=26)
        self.entry_user.grid(row=0, column=1, padx=10, pady=4)

        tk.Label(frame_inputs, text="Senha:", bg="#1e1e2e", fg="#aaa",
                 font=("Arial", 10)).grid(row=1, column=0, sticky="w", pady=4)
        self.entry_pass = tk.Entry(frame_inputs, font=("Arial", 11), bg="#2e2e3e",
                                   fg="white", insertbackground="white",
                                   relief=tk.FLAT, width=26, show="●")
        self.entry_pass.grid(row=1, column=1, padx=10, pady=4)

        def toggle_pass():
            if self.entry_pass.cget("show") == "●":
                self.entry_pass.config(show="")
                btn_eye.config(text="👁")
            else:
                self.entry_pass.config(show="●")
                btn_eye.config(text="🔒")

        btn_eye = tk.Button(frame_inputs, text="🔒", bg="#2e2e3e", fg="#aaa",
                            relief=tk.FLAT, cursor="hand2", font=("Arial", 11),
                            width=2, command=toggle_pass)
        btn_eye.grid(row=1, column=2, padx=2)

        frame_btns = tk.Frame(self, bg="#1e1e2e")
        frame_btns.pack(pady=10)
        self.btn_connect = tk.Button(frame_btns, text="Conectar", width=14, height=2,
                                     font=("Arial", 11, "bold"), bg="#4CAF50", fg="white",
                                     relief=tk.FLAT, cursor="hand2", command=self.connect)
        self.btn_connect.pack(side=tk.LEFT, padx=10)
        self.btn_disconnect = tk.Button(frame_btns, text="Desconectar", width=14, height=2,
                                        font=("Arial", 11, "bold"), bg="#f44336", fg="white",
                                        relief=tk.FLAT, cursor="hand2", command=self.disconnect)
        self.btn_disconnect.pack(side=tk.LEFT, padx=10)

        tk.Label(self, text="Log:", font=("Arial", 9),
                 bg="#1e1e2e", fg="#888").pack(anchor="w", padx=20)
        frame_log = tk.Frame(self, bg="#1e1e2e")
        frame_log.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 20))
        self.log_text = tk.Text(frame_log, height=6, bg="#0d0d1a", fg="#aaa",
                                font=("Monospace", 8), relief=tk.FLAT)
        self.log_text.pack(fill=tk.BOTH, expand=True)

    def refresh_list(self):
        self.listbox.delete(0, tk.END)
        for p in self.config_data["profiles"]:
            self.listbox.insert(tk.END, f"  {p['name']}  —  {p['server']}")
        if self.config_data["profiles"]:
            self.listbox.selection_set(0)
            self.on_select(None)

    def on_select(self, event):
        sel = self.listbox.curselection()
        if sel:
            self.selected_profile = self.config_data["profiles"][sel[0]]
            self.entry_user.delete(0, tk.END)
            self.entry_user.insert(0, self.selected_profile.get("username", ""))

    def new_profile(self):
        dialog = ProfileDialog(self)
        self.wait_window(dialog)
        if dialog.result:
            self.config_data["profiles"].append(dialog.result)
            save_config(self.config_data)
            self.refresh_list()

    def edit_profile(self):
        if not self.selected_profile:
            return
        dialog = ProfileDialog(self, self.selected_profile)
        self.wait_window(dialog)
        if dialog.result:
            idx = self.config_data["profiles"].index(self.selected_profile)
            self.config_data["profiles"][idx] = dialog.result
            save_config(self.config_data)
            self.selected_profile = dialog.result
            self.refresh_list()

    def delete_profile(self):
        if not self.selected_profile:
            return
        if messagebox.askyesno("Confirmar", f"Excluir perfil '{self.selected_profile['name']}'?"):
            self.config_data["profiles"].remove(self.selected_profile)
            save_config(self.config_data)
            self.selected_profile = None
            self.refresh_list()

    def update_status(self):
        self.after(0, lambda: (
            self.status_label.config(text="Verificando...", fg="gray"),
            self.status_dot.config(fg="gray")
        ))

        def check():
            status = get_status(_senha_sudo or "")
            def apply():
                if status == "conectado":
                    self.status_label.config(text="Conectado", fg="#4CAF50")
                    self.status_dot.config(text="●", fg="#4CAF50")
                    self.btn_connect.config(state=tk.DISABLED)
                    self.btn_disconnect.config(state=tk.NORMAL)
                else:
                    self.status_label.config(text="Desconectado", fg="#f44336")
                    self.status_dot.config(text="●", fg="#f44336")
                    self.btn_connect.config(state=tk.NORMAL)
                    self.btn_disconnect.config(state=tk.DISABLED)
            self.after(0, apply)

        threading.Thread(target=check, daemon=True).start()

    def connect(self):
        self.config_data = load_config()
        self.refresh_list()
        if not self.selected_profile:
            messagebox.showerror("Erro", "Selecione um perfil!")
            return
        usuario = self.entry_user.get().strip()
        senha = self.entry_pass.get().strip()
        if not usuario or not senha:
            messagebox.showerror("Erro", "Preencha usuário e senha!")
            return
        if usuario != self.selected_profile.get("username", "") or \
                senha != self.selected_profile.get("password", ""):
            messagebox.showerror("Erro", "Usuário ou senha incorretos!")
            return

        senha_sudo = self._obter_senha_sudo()
        if not senha_sudo:
            return

        self.btn_connect.config(state=tk.DISABLED)
        self.status_label.config(text="Conectando...", fg="orange")
        self.status_dot.config(text="●", fg="orange")
        self.log_text.delete(1.0, tk.END)

        def do_connect():
            profile = self.selected_profile
            server = profile["server"]
            psk = profile["preshared_key"]
            conn_name = profile["name"]

            self._log(f"Resolvendo IP de {server}...\n")
            ip = resolve_ip(server)
            if not ip:
                self._log("Erro: não foi possível resolver o IP do servidor!\n")
                self.after(0, self.update_status)
                return
            self._log(f"IP resolvido: {ip}\n")

            secrets = f'%any {ip} : PSK "{psk}"\n{usuario} : XAUTH "{senha}"\n'
            write_as_root("/etc/ipsec.secrets", secrets, senha_sudo)

            conf = f"""config setup
    charondebug="ike 1, knl 1"

conn {conn_name}
    keyexchange=ikev1
    authby=xauthpsk
    xauth=client
    left=%defaultroute
    leftid={usuario}
    right={server}
    rightid={ip}
    rightsubnet=10.244.0.0/16
    ike=aes128-sha256-modp1536,aes256-sha256-modp1536,aes128-sha256-modp2048,aes256-sha256-modp2048
    esp=aes128-sha256-modp1536,aes256-sha256-modp1536,aes128-sha256-modp1024,aes256-sha256-modp1024
    leftsourceip=%config
    auto=add
"""
            write_as_root("/etc/ipsec.conf", conf, senha_sudo)

            self._log("Reiniciando IPsec...\n")

            script = (
                f"ipsec down {conn_name} 2>/dev/null; true\n"
                "sleep 1\n"
                "if ! ipsec statusall 2>/dev/null | grep -qi 'charon.*running\\|daemon.*running'; then\n"
                "    ipsec start\n"
                "    sleep 3\n"
                "fi\n"
                "ipsec rereadall 2>/dev/null; true\n"
                "ipsec reload 2>/dev/null; true\n"
                "sleep 1\n"
                f"ipsec up {conn_name}\n"
            )

            script_path = None
            out_parts = []
            try:
                with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as sf:
                    sf.write(script)
                    script_path = sf.name

                proc = subprocess.Popen(
                    ["sudo", "-S", "bash", script_path],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                proc.stdin.write((senha_sudo + "\n").encode())
                proc.stdin.close()

                for line in iter(proc.stdout.readline, b""):
                    chunk = line.decode("utf-8", errors="replace")
                    out_parts.append(chunk)
                    self._log(chunk)

                proc.wait(timeout=120)
            except Exception as e:
                self._log(f"Erro: {e}\n")
            finally:
                if script_path:
                    try:
                        os.unlink(script_path)
                    except OSError:
                        pass

            out = "".join(out_parts)

            if "established successfully" not in out.lower():
                self._log("Falha na conexão. Verifique as credenciais e tente novamente.\n")
                self.after(0, self.update_status)
                return

            dns = None
            for line in out.splitlines():
                if "installing DNS server" in line:
                    parts = line.split("installing DNS server")
                    if len(parts) > 1:
                        dns = parts[1].split()[0].strip()
                        break
            if not dns:
                dns = profile.get("dns", "10.244.130.6")
            self._log(f"DNS detectado: {dns}\n")
            write_as_root("/etc/resolv.conf", f"nameserver {dns}\nnameserver 8.8.8.8\n", senha_sudo)
            self.after(0, self.update_status)

        threading.Thread(target=do_connect, daemon=True).start()

    def disconnect(self):
        if not self.selected_profile:
            return

        senha_sudo = self._obter_senha_sudo()
        if not senha_sudo:
            return

        self.btn_disconnect.config(state=tk.DISABLED)
        self.status_label.config(text="Desconectando...", fg="orange")
        self.status_dot.config(text="●", fg="orange")
        self.log_text.delete(1.0, tk.END)

        def do_disconnect():
            out = sudo_run(["ipsec", "down", self.selected_profile["name"]], senha_sudo, timeout=15)
            write_as_root("/etc/resolv.conf", "nameserver 8.8.8.8\n", senha_sudo)
            self._log(out)
            self.after(0, self.update_status)

        threading.Thread(target=do_disconnect, daemon=True).start()


if __name__ == "__main__":
    app = VPNManager()
    app.mainloop()
