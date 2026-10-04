"""Offline recovery for an installation's saved listener. Run with the app stopped."""
import argparse
import app_paths
import dbcore
import network_settings
import runtime_guard
import security


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--port',required=True,type=int)
    args=parser.parse_args()
    base=app_paths.application_root()
    db=base/'tvmanager.db'
    if not db.is_file():
        parser.error('No existing tvmanager.db found in the installation directory.')
    try:
        runtime_guard.acquire(base)
        with dbcore.connect(db,readonly=True,wal=False) as c:
            admin=bool(c.execute('SELECT 1 FROM admin_users WHERE enabled=1 LIMIT 1').fetchone())
            auth=c.execute("SELECT value FROM settings WHERE lower(section)='tvmanager' AND lower(name)='browser_auth_enabled'").fetchone()
        result=network_settings.save(db,vars(args),admin,security.as_bool(auth[0] if auth else '0'),environ={})
    except (ValueError,RuntimeError) as error:
        parser.error(str(error))
    print(f"Saved {result['host']}:{result['port']}. Start TV Manager normally. Browser security is unchanged.")


if __name__=='__main__':
    main()
