MOG_PASSWORD = "supersecretpasswordformeonly"


def master_sql(hostname):
    return f"SELECT id, hostname FROM hosts WHERE hostname = '{hostname}'"


def mog(check_connection):
    return check_connection(user="mog", password=MOG_PASSWORD)


def set_session_cookie(response, token):
    response.set_cookie("workbench_session", token, secure=True, httponly=False, samesite="Strict")
    return response
