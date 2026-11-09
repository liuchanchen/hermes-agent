#!/usr/bin/env python3
"""
pexpect-ssh.py — Password-based SSH via pexpect for Hermes environments
where sshpass is not installed.

Usage:
  python3 pexpect-ssh.py <host> <user> <password> <command>

Hermes invocation (execute_code):
  from hermes_tools import terminal
  result = terminal("python3 pexpect-ssh.py 192.168.x.x jianliu '!QAZ2wsx' 'hostname'")

Requirements:
  pip install pexpect  (usually pre-installed in Hermes env)

Returns: stdout + exit_code. On failure, error output is printed to stderr.
"""

import sys, os, time, pexpect, textwrap

def ssh_exec(host, user, password, command, timeout=15):
    """Execute a command on a remote host via SSH with password auth."""
    cmd = (
        f'ssh -o StrictHostKeyChecking=no '
        f'-o ConnectTimeout={min(timeout - 5, 10)} '
        f'-o PreferredAuthentications=password '
        f'-o PubkeyAuthentication=no '
        f'{user}@{host}'
    )

    child = pexpect.spawn(cmd, timeout=timeout, encoding='utf-8')
    # Common prompt patterns
    i = child.expect(
        ['password:', 'Permission denied', pexpect.TIMEOUT, pexpect.EOF],
        timeout=timeout
    )

    if i != 0:
        print(f"SSH connection failed (expect code {i})", file=sys.stderr)
        print(child.before or '', file=sys.stderr)
        return 1

    child.sendline(password)
    # Short grace window for password auth to complete
    i = child.expect(
        ['\$', '#', 'Permission denied', 'password:', pexpect.TIMEOUT],
        timeout=10
    )

    if i in (2, 3):
        print(f"Authentication failed (expect code {i})", file=sys.stderr)
        print(child.before or '', file=sys.stderr)
        child.close()
        return 2
    if i == 4:
        # Slow .bashrc — try to send command anyway; it may have already
        # authenticated and just hasn't shown the prompt yet
        pass

    # Two-step approach to avoid all PTY/shell/prompt parsing:
    #   Step 1: run command → write output to temp file, echo DONE marker
    #   Step 2: cat the temp file to read the actual result
    pid = os.getpid()
    # Very long hex marker (128 chars) — impossible to appear in echoed bash
    # command string, so pexpect must wait for the actual echo output
    marker = 'HM_' + os.urandom(64).hex()[:64]
    tmp_out = f'/tmp/_hssh_{pid}_out.txt'
    # Output marker on its OWN line so only the real echo output matches
    wrapped = f'/bin/bash --norc --noprofile -c "exec 2>&1; {command} > {tmp_out} 2>&1; cat {tmp_out}; rm -f {tmp_out}; echo; echo {marker}"'
    child.sendline(wrapped)
    try:
        # regex: anchor marker to end-of-line so it only matches actual output
        child.expect([marker + '\r\n'], timeout=timeout)
    except pexpect.TIMEOUT:
        print(f"Timeout waiting for marker", file=sys.stderr)
        print(child.before[-500:] if child.before else '', file=sys.stderr)
        child.close()
        return 3
    output = child.before or ''
    child.close()

    # Parse: before=echoed_command + cat_output + blank + marker
    # Remove lines containing the echoed /bin/bash wrapper and marker
    lines = output.splitlines()
    clean = [l for l in lines if marker not in l and '/bin/bash' not in l and marker not in l]
    print('\n'.join(clean).strip())
    return 0


if __name__ == '__main__':
    if len(sys.argv) < 5:
        print(textwrap.dedent("""\
            Usage: python3 pexpect-ssh.py <host> <user> <password> <command>
            Example: python3 pexpect-ssh.py 192.168.12.12 jianliu '0' 'hostname'
        """), file=sys.stderr)
        sys.exit(1)

    host = sys.argv[1]
    user = sys.argv[2]
    password = sys.argv[3]
    command = sys.argv[4]
    timeout = int(sys.argv[5]) if len(sys.argv) > 5 else 20

    sys.exit(ssh_exec(host, user, password, command, timeout))
