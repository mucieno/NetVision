import os
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify
from netmiko import ConnectHandler

# =====================================
#CONFIGURATION & SECURITY
# =====================================

# Load SSH credentials from an external .env file
load_dotenv()

app = Flask(__name__)

# === USER CONFIG (Prioritize ENV) ====
USERNAME = os.getenv("SSH_USERNAME")
PASSWORD = os.getenv("SSH_PASSWORD")
SECRET = os.getenv("SSH_SECRET")
TIMEOUT = 8
# =====================================

COMMANDS = {
    'hostname': 'show run | inc hostname',
    'notconnect': 'show interface status | include notconnect',
    'notconnect_alt': 'show interface description | include notconnect',
    'errors': 'show interface counter error',
    'log_tail': 'show log',
    'cpu': 'show process cpu sorted',
    'env': 'show env all',
    'duplex': 'show interface status | include half'
}

LOG_TAIL_LINES = 10
CPU_HEAD_LINES = 5

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/run', methods=['POST'])
def run_commands():
    data = request.json or {}
    ip = data.get('ip')

    if not ip:
        return jsonify({'error': 'missing ip'}), 400

    device = {
        'device_type': 'cisco_ios',
        'host': ip,
        'username': USERNAME,
        'password': PASSWORD,
        'secret': SECRET,
        'timeout': TIMEOUT,
    }

    results = {}

    try:
        with ConnectHandler(**device) as net_conn:
            try:
                net_conn.enable()
            except:
                pass

            # 1) Hostname
            out_host = net_conn.send_command(COMMANDS['hostname'])
            if out_host.strip():
                parts = out_host.strip().splitlines()[0].split(maxsplit=1)
                results['hostname'] = parts[1] if len(parts) > 1 else '(unknown)'
            else:
                results['hostname'] = '(unknown)'

            # 2) Notconnect
            out_nc = net_conn.send_command(COMMANDS['notconnect'])
            if '% Invalid input' in out_nc:
                out_nc = net_conn.send_command(COMMANDS['notconnect_alt'])
            results['notconnect'] = out_nc.strip() or '(no output)'

            # 3) Errors
            out_err = net_conn.send_command(COMMANDS['errors'])
            filtered_err = [l for l in out_err.strip().splitlines() 
                            if any(p.isdigit() and int(p) > 0 for p in l.split()[1:])]
            results['errors'] = '\n'.join(filtered_err) if filtered_err else '(no errors found)'

            # 4) Log tail
            out_log = net_conn.send_command(COMMANDS['log_tail']).strip().splitlines()
            results['log_tail'] = '\n'.join(out_log[-LOG_TAIL_LINES:]) if out_log else '(no output)'

            # 5) CPU
            out_cpu = net_conn.send_command(COMMANDS['cpu']).strip().splitlines()
            results['cpu'] = '\n'.join(out_cpu[:CPU_HEAD_LINES]) if out_cpu else '(no output)'

            # 6) Env
            out_env = net_conn.send_command(COMMANDS['env']).strip().splitlines()
            results['env'] = '\n'.join(out_env[:6]) if out_env else '(no output)'

            # 7) Duplex
            results['duplex'] = net_conn.send_command(COMMANDS['duplex']).strip() or '(no output)'

    except Exception as e:
        return jsonify({'error': 'connection failed', 'details': str(e)}), 500

    return jsonify({'results': results})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
