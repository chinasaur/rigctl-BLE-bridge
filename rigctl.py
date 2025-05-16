import select
import subprocess
import time


def connect(serial_device_path: str, hamlib_device: int) -> subprocess.Popen:
    cmd = ["/usr/bin/rigctl", "-r", serial_device_path, "-m", str(hamlib_device)]
    print('Starting subprocess:', cmd)
    return subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class RigctlSubprocess:
    USER_PROMPT = "Rig command: "  # Filter this superfluous message out of replies.
    TERMINATE_WAIT_SECS = 2.0

    def __init__(self, serial_device_path: str, hamlib_device: int):
        self.serial_device_path = serial_device_path
        self.hamlib_device = hamlib_device
        self.subprocess = connect(serial_device_path, hamlib_device)

    def terminate_and_wait(self):
        """Attempt to terminate subprocess.

        Since only one process can connect to a given serial port at once, it is worth being
        a bit slow here to try to ensure the process is dead.
        """
        if self.subprocess is None:
            return

        print("Terminating existing rigctl subprocess:", serial_device_path)
        self.subprocess.terminate()
        try:
            self.subprocess.wait(timeout=self.TERMINATE_WAIT_SECS)
        except subprocess.TimeoutExpired as e:
            print("terminate timeout:", e)

        self.subprocess.kill()
        try:
            self.subprocess.wait(timeout=self.TERMINATE_WAIT_SECS)
        except subprocess.TimeoutExpired as e:
            print("kill timeout:", e)

    def reconnect(self):
        self.terminate_and_wait()
        self.subprocess = connect(self.serial_device_path, self.hamlib_device)
        return None

    def select(self):
        """Query OS for which pipes are ready / errored."""
        readable = [self.subprocess.stdout, self.subprocess.stderr]
        writable = [self.subprocess.stdin]
        errored = [self.subprocess.stdout, self.subprocess.stderr, self.subprocess.stdin]
        return select.select(readable, writable, errored)

    def poll(self):
        retval = self.subprocess.poll()
        if retval is not None:
            print(f"rigctl on {self.serial_device_path} found to be dead with retval {retval}")
        return retval

    def write(self, cmd_str: str) -> int | None:
        # If we detect that subprocess has gone bad, try to restart it, but give up on writing for now.
        _, writable, errored = self.select()
        if errored:
            print("Error on rigctl pipes.")
            return self.reconnect()
        if not writable:
            print("rigctl stdin not writable.")
            return self.reconnect()
        assert len(writable) == 1

        cmd_str = cmd_str.strip() + "\n"  # rigctl is better behaved this way.
        try:
            written = writable[0].write(cmd_str.encode())
            writable[0].flush()
        except BrokenPipeError as e:
            print(e)
            return self.reconnect()
        return written

    def safe_read(self, pipe) -> str | None:
        """Try to ensure we avoid hanging while reading pipes."""
        readable, _, _ = self.select()
        if pipe not in readable:
            return None
        l = len(pipe.peek())
        return pipe.read(l).decode()

    def parse(self, out: str) -> str:
        """Clean up output."""
        lines = out.replace(self.USER_PROMPT, "").split("\n")
        return "; ".join(l for l in lines if l)  # Drop any empty ones.

    # TODO(K6PLI): Probably change to returning a single str with any error
    # condition spelled out.
    def read(self) -> tuple[str | None, str | None]:
        _, _, errored = self.select()
        if errored:
            print("Error on rigctl pipes.")
            self.reconnect()
            return None, None

        out = self.safe_read(self.subprocess.stdout)
        if out is not None and not out:
            # An empty reply is valid for set commands, but it can also indicate the process died.
            if self.poll() is None:
                out = "Command accepted."
            else:
                self.reconnect()
                out = None
        if out is not None:
            out = self.parse(out)

        err = self.safe_read(self.subprocess.stderr)
        if err:
            print(err)

        return out, err

    def waitread(self, timeout_secs: float) -> tuple[str | None, str | None]:
        """Recursively check if output is available up to timeout_secs."""
        start = time.time()
        out, err = None, None
        if timeout_secs <= 0.0:
            return None, None

        readable, _, errored = self.select()
        if readable:
            out, err = self.read()
        if errored:
            print("Error on rigctl pipes.")
            self.reconnect()
        if readable:
            return out, err

        time.sleep(0.1)
        elapsed = time.time() - start
        return self.waitread(timeout_secs - elapsed)


class RigctlManager:

    def __init__(self):
        # Only one process can connect to a given serial device path at a time.
        self.rigctl_from_serial_device = {}

    def maybe_terminate_existing(self, serial_device_path: str):
        existing_rigctl = self.rigctl_from_serial_device.get(serial_device_path)
        if existing_rigctl is None:
            return
        if existing_rigctl.poll() is not None:
            return  # Already dead.
        existing_rigctl.terminate_and_wait()

    def refresh(self, serial_device_path: str, hamlib_device: int):
        self.maybe_terminate_existing(serial_device_path)
        self.rigctl_from_serial_device[serial_device_path] = RigctlSubprocess(serial_device_path, hamlib_device)

    def get_rigctl(self, serial_device_path: str, hamlib_device: int) -> RigctlSubprocess:
        if serial_device_path not in self.rigctl_from_serial_device:
            self.refresh(serial_device_path, hamlib_device)
        if self.rigctl_from_serial_device[serial_device_path].hamlib_device != hamlib_device:
            # The Hamlib device ID for this serial port has changed, so we need to get a new
            # RigctlSubprocess.
            self.refresh(serial_device_path, hamlib_device)
        if self.rigctl_from_serial_device[serial_device_path].poll() is not None:
            # Subprocess died for some reason; try restarting.
            self.refresh(serial_device_path, hamlib_device)
        return self.rigctl_from_serial_device[serial_device_path]

    def cleanup(self, valid_serial_device_paths: frozenset[str]):
        for serial_device_path, rigctl in self.rigctl_from_serial_device.items():
            if serial_device_path in valid_serial_device_paths:
                continue
            # Serial port no longer detected, so clear out any rigctl that was previously
            # connected to it. We don't want to wait for this though.
            rigctl.subprocess.terminate()
            self.rigctl_from_serial_device.pop(serial_device_path, None)
