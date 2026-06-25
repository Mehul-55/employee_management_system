"""
╔══════════════════════════════════════════════╗
║   Employee Management System                 ║
║   main.py - Entry Point                      ║
║   Run: python main.py                        ║
╚══════════════════════════════════════════════╝
"""

import os
import json
import sys
import subprocess
import threading
import time
from urllib import error, parse, request
sys.path.append(os.path.dirname(os.path.abspath(__file__)))


def get_api_base_url():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    return os.getenv("API_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def _api_health_url():
    return f"{get_api_base_url()}/api/health"


def is_api_running(timeout=1.5):
    try:
        with request.urlopen(_api_health_url(), timeout=timeout) as response:
            return 200 <= response.status < 500
    except Exception:
        return False


def start_api_server():
    api_base = get_api_base_url()
    parsed = parse.urlparse(api_base)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000
    if host not in {"127.0.0.1", "localhost"}:
        print(f"  WARNING API auto-start skipped for non-local host: {api_base}")
        return False

    base_dir = os.path.dirname(os.path.abspath(__file__))
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

    try:
        subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "api_main:app",
                "--host",
                host,
                "--port",
                str(port),
            ],
            cwd=base_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            creationflags=creationflags,
        )
        return True
    except Exception as exc:
        print(f"  ERROR Could not auto-start API server -> {exc}")
        return False


def ensure_api_server():
    print("[CHECK] Checking API server...")
    if is_api_running():
        print(f"  OK API server already running at {get_api_base_url()}\n")
        return True

    print("  INFO API server is not running. Starting it automatically...")
    if not start_api_server():
        print("  WARNING Start run_api.bat manually, then run the app again.\n")
        return False

    for _ in range(20):
        time.sleep(0.5)
        if is_api_running(timeout=1):
            print(f"  OK API server started at {get_api_base_url()}\n")
            return True

    print("  WARNING API server did not become ready in time.")
    print("     Check run_api.bat or run: python -m uvicorn api_main:app --host 127.0.0.1 --port 8000\n")
    return False


# ══════════════════════════════════════════════
#  STEP 1 - Check pip packages installed
# ══════════════════════════════════════════════
def check_dependencies():
    required = {
        "PyQt6":   "PyQt6",
        "pymongo": "pymongo",
        "dns":     "dnspython",
        "dotenv":  "python-dotenv",
        "fastapi": "fastapi",
        "uvicorn": "uvicorn",
    }
    missing = []
    for module, pip_name in required.items():
        try:
            __import__(module)
            print(f"  OK {pip_name} - installed")
        except ImportError:
            print(f"  ERROR {pip_name} - NOT installed")
            missing.append(pip_name)

    if missing:
        print(f"\nWARNING  Run: pip install {' '.join(missing)}\n")
        return False

    print("  OK All dependencies satisfied.\n")
    return True


# ══════════════════════════════════════════════
#  STEP 2 - Check project files load correctly
#  GUI is compiled here instead of imported because
#  QApplication is created later inside launch().
# ══════════════════════════════════════════════
def check_project_imports():
    import py_compile

    project_modules = [
        ("db_config",      "MongoDB configuration", "import"),
        ("auth_model",    "Auth logic",            "import"),
        ("attendance",    "Attendance logic",      "import"),
        ("shift_model",   "Shift and salary logic", "import"),
        ("audit_log",     "Audit logging",         "import"),
        ("employee_model", "Employee data model",   "import"),
        ("gui_pyqt6",     "PyQt GUI module",       "compile"),
    ]
    all_ok = True
    base_dir = os.path.dirname(os.path.abspath(__file__))

    for module, description, check_type in project_modules:
        try:
            if check_type == "compile":
                # Do not import the GUI before QApplication exists; compile catches syntax/load issues safely.
                py_compile.compile(os.path.join(base_dir, f"{module}.py"), doraise=True)
            else:
                __import__(module)
            print(f"  OK {module}.py - {description}")
        except Exception as e:
            print(f"  ERROR {module}.py - {description} -> {e}")
            all_ok = False
    return all_ok


# ══════════════════════════════════════════════
#  STEP 3 - Ping MongoDB
# ══════════════════════════════════════════════
def check_db_connection():
    try:
        import db_config
        db_config.client.admin.command("ping")
        print(f"  OK {db_config.connection_label()} connected successfully.")
        print(f"  OK Database selected: {db_config.DB_NAME}\n")
        try:
            import db_indexes
            created = db_indexes.ensure_indexes()
            print(f"  OK MongoDB indexes ready ({len(created)} checked).\n")
        except Exception as index_error:
            print(f"  WARNING MongoDB indexes could not be checked -> {index_error}\n")
        return True
    except Exception as e:
        print(f"  ERROR MongoDB connection failed -> {e}")
        print("     For local MongoDB: make sure MongoDB is running on localhost:27017.")
        print("     For MongoDB Atlas: check username, password, database user permissions,")
        print("     and Network Access IP allowlist in the Atlas dashboard.\n")
        return False


# ══════════════════════════════════════════════
#  APPLICATION CONTROLLER
# ══════════════════════════════════════════════
class ApplicationController:
    def __init__(self):
        self._app          = None
        self._current_user = None   # tracks who is logged in for audit logging
        self._current_role = None   # admin or employee for permission checks

    def set_app(self, app):
        self._app = app

    def show_login(self):
        # Log logout before clearing the dashboard
        try:
            from audit_log import log_action
            if self._current_user:
                log_action("LOGOUT", self._current_user,
                           details=f"User '{self._current_user}' logged out.")
        except Exception as e:
            print(f"WARNING  Audit log (logout) failed: {e}")
        self._current_user = None
        self._current_role = None
        if self._app:
            self._app._show_login()

    def handle_login(self, mode, username, password, err_label):
        try:
            auth_response = self._api_login(mode, username, password)

            session_user = username if mode == "admin" else str(auth_response["user_id"])
            dashboard_role = "admin" if mode == "admin" else str(auth_response["user_id"])
            self._current_user = session_user
            self._current_role = "admin" if mode == "admin" else "employee"

            elapsed_ms = auth_response.get("elapsed_ms")
            if elapsed_ms is not None:
                print(f"API login verified in {elapsed_ms} ms.")

            self._app.load_dashboard(dashboard_role, session_user)

            threading.Thread(
                target=self._log_login_async,
                args=(mode, session_user),
                daemon=True,
            ).start()

        except Exception as e:
            print(f"ERROR API login error: {e}")
            err_label.setText(str(e))

    def _log_login_async(self, mode, session_user):
        try:
            from audit_log import log_action
            log_action(
                "LOGIN",
                session_user,
                details=f"{mode.capitalize()} '{session_user}' logged in successfully through API.",
            )
        except Exception as e:
            print(f"Audit log (login) failed: {e}")

    def _api_login(self, mode, username, password):
        endpoint = "/api/auth/admin-login" if mode == "admin" else "/api/auth/employee-login"
        payload = {
            "username": username,
            "password": password,
        } if mode == "admin" else {
            "emp_id": username,
            "password": password,
        }
        data = json.dumps(payload).encode("utf-8")
        api_request = request.Request(
            f"{get_api_base_url()}{endpoint}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(api_request, timeout=8) as response:
                return json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            message = exc.reason
            try:
                body = json.loads(exc.read().decode("utf-8"))
                message = body.get("detail") or message
            except Exception:
                pass
            raise RuntimeError(message)
        except error.URLError:
            raise RuntimeError(
                "API server is not responding. Restart the app, or run run_api.bat to see API errors."
            )
        except TimeoutError:
            raise RuntimeError("API login timed out. Check the API server and database connection.")

    def is_admin(self):
        return self._current_role == "admin"

    def is_employee(self):
        return self._current_role == "employee"

    def current_user(self):
        return self._current_user

    def _admin_denied(self):
        return False, "Admin permission required."

    def get_emp_id_by_username(self, username):
        if self._current_role is None:
            return None
        if self.is_employee() and str(username) != str(self._current_user):
            return None
        import auth_model
        try:
            return auth_model.get_emp_id_by_username(username)
        except Exception as e:
            print(f"ERROR get_emp_id_by_username error: {e}")
            return None

    def account_exists(self, employee_id):
        if not self.is_admin():
            return False
        import auth_model
        try:
            return auth_model.account_exists(employee_id)
        except Exception as e:
            print(f"ERROR account_exists error: {e}")
            return False

    def register_employee(self, employee_id, name, password, basic_salary=0, department=None,
                          email=None, phone=None, address=None, joining_date=None):
        if not self.is_admin():
            return self._admin_denied()
        import auth_model
        try:
            return auth_model.register_employee(
                employee_id, name, password, basic_salary, department,
                email=email, phone=phone, address=address, joining_date=joining_date,
            )
        except Exception as e:
            print(f"Registration error: {e}")
            return False, "Registration failed due to a system error."

    def update_employee_details(self, employee_id, name, basic_salary=0, department=None,
                                email=None, phone=None, address=None, joining_date=None):
        if not self.is_admin():
            return self._admin_denied()
        import auth_model
        try:
            return auth_model.update_employee_details(
                employee_id, name, basic_salary, department,
                email=email, phone=phone, address=address, joining_date=joining_date,
            )
        except Exception as e:
            print(f"Update employee error: {e}")
            return False, "Employee update failed due to a system error."

    def get_departments(self):
        if not self.is_admin():
            return []
        import auth_model
        try:
            return auth_model.get_departments()
        except Exception as e:
            print(f"Department load error: {e}")
            return []

    def delete_emp_account(self, employee_id):
        if not self.is_admin():
            return self._admin_denied()
        import auth_model
        try:
            return auth_model.delete_emp_account(employee_id)
        except Exception as e:
            print(f"Delete employee error: {e}")
            return False, "Deletion failed due to a system error."

    def reset_password(self, employee_id, new_password):
        if not self.is_admin():
            return self._admin_denied()
        import auth_model
        try:
            return auth_model.reset_password(employee_id, new_password)
        except Exception as e:
            print(f"ERROR reset_password error: {e}")
            return False, "Reset failed due to a system error."

    def change_password(self, username, old_password, new_password):
        if self._current_role is None:
            return False, "Login required."
        if self.is_employee() and str(username) != str(self._current_user):
            return False, "You can only change your own password."
        import auth_model
        try:
            return auth_model.change_password(username, old_password, new_password)
        except Exception as e:
            print(f"ERROR change_password error: {e}")
            return False, "Password change failed due to a system error."

    def get_all_employees(self, include_deleted=False):
        if not self.is_admin():
            return []
        import auth_model
        try:
            return auth_model.get_all_employees(include_deleted=include_deleted)
        except Exception as e:
            print(f"ERROR get_all_employees error: {e}")
            return []

    def restore_employee(self, emp_id):
        if not self.is_admin():
            return self._admin_denied()
        import auth_model
        try:
            ok, message = auth_model.restore_employee(emp_id)
            if ok:
                try:
                    from audit_log import log_action
                    log_action(
                        "RESTORE_EMPLOYEE",
                        self._current_user or "admin",
                        target=str(emp_id),
                        details=f"Employee ID {emp_id} was restored.",
                    )
                except Exception as audit_error:
                    print(f"WARNING Audit log (restore employee) failed: {audit_error}")
            return ok, message
        except Exception as e:
            print(f"ERROR restore_employee error: {e}")
            return False, "Restore failed due to a system error."

    def launch(self):
        """Create QApplication FIRST, then import and build the GUI."""
        from PyQt6.QtWidgets import QApplication
        from PyQt6.QtGui import QFont
        from PyQt6.QtCore import QTimer
        import gui_pyqt6

        print("[START] Launching Employee Management System...")
        print("=" * 48)

        qt_app = QApplication(sys.argv)          # OK QApplication before any widget
        qt_app.setFont(QFont("Segoe UI", 13))

        self._app = gui_pyqt6.App(self)          # OK Now safe to create widgets
        self._app.show()
        QTimer.singleShot(0, self._app._titlebar.maximize_to_screen)
        sys.exit(qt_app.exec())                  # OK PyQt6 uses exec(), not exec_()


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════
if __name__ == "__main__":
    print("=" * 48)
    print("   Employee Management System - Starting")
    print("=" * 48)

    print("\n[CHECK] Checking dependencies...")
    if not check_dependencies():
        sys.exit(1)

    print("[CHECK] Checking project modules...")
    if not check_project_imports():
        print("\nWARNING  Fix the errors above before running.")
        sys.exit(1)

    print("[CHECK]  Checking database connection...")
    if not check_db_connection():
        print("WARNING  Cannot start without database connection.")
        sys.exit(1)

    if not ensure_api_server():
        print("WARNING  Cannot start without API server.")
        sys.exit(1)

    controller = ApplicationController()
    controller.launch()
