import argparse

from sqlalchemy import inspect

from app import AgentLog, Assignment, CalendarEvent, ClassSession, app, db


OWNED_MODELS = (Assignment, ClassSession, CalendarEvent, AgentLog)


def migrate():
    dialect = db.engine.dialect.name
    if dialect not in {"mysql", "sqlite"}:
        raise RuntimeError(f"Unsupported migration database: {dialect}")

    db.create_all()
    inspector = inspect(db.engine)
    preparer = db.engine.dialect.identifier_preparer

    for model in OWNED_MODELS:
        table = model.__tablename__
        quoted_table = preparer.quote(table)
        columns = {column["name"] for column in inspector.get_columns(table)}
        if "user_id" not in columns:
            if dialect == "sqlite":
                statement = (
                    f"ALTER TABLE {quoted_table} "
                    "ADD COLUMN user_id INTEGER REFERENCES users(id)"
                )
                with db.engine.begin() as connection:
                    connection.exec_driver_sql(statement)
            else:
                with db.engine.begin() as connection:
                    connection.exec_driver_sql(
                        f"ALTER TABLE {quoted_table} ADD COLUMN user_id INTEGER NULL"
                    )
                    connection.exec_driver_sql(
                        f"ALTER TABLE {quoted_table} "
                        f"ADD CONSTRAINT fk_{table}_user_id_users "
                        "FOREIGN KEY (user_id) REFERENCES users(id)"
                    )
            print(f"Added nullable user ownership to {table}.")

        inspector = inspect(db.engine)
        foreign_keys = inspector.get_foreign_keys(table)
        has_user_fk = any(
            foreign_key.get("constrained_columns") == ["user_id"]
            and foreign_key.get("referred_table") == "users"
            for foreign_key in foreign_keys
        )
        if not has_user_fk:
            if dialect == "sqlite":
                raise RuntimeError(
                    f"{table}.user_id exists without its users foreign key; "
                    "inspect the schema and apply a reviewed migration."
                )
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    f"ALTER TABLE {quoted_table} "
                    f"ADD CONSTRAINT fk_{table}_user_id_users "
                    "FOREIGN KEY (user_id) REFERENCES users(id)"
                )

        index_name = f"ix_{table}_user_id"
        indexes = {index["name"] for index in inspector.get_indexes(table)}
        if index_name not in indexes:
            with db.engine.begin() as connection:
                connection.exec_driver_sql(
                    f"CREATE INDEX {preparer.quote(index_name)} "
                    f"ON {quoted_table} (user_id)"
                )

    print(
        "Migration complete. Existing rows were preserved with user_id NULL; "
        "they are not visible to authenticated accounts."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Add user authentication ownership columns without deleting records."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Report migration readiness without changes.")
    mode.add_argument("--apply", action="store_true", help="Create missing tables and add ownership columns.")
    args = parser.parse_args()

    with app.app_context():
        if args.check:
            inspector = inspect(db.engine)
            for model in OWNED_MODELS:
                table = model.__tablename__
                if table not in inspector.get_table_names():
                    print(f"{table}: missing (will be created)")
                elif "user_id" in {
                    column["name"] for column in inspector.get_columns(table)
                }:
                    print(f"{table}: user_id present")
                else:
                    print(f"{table}: user_id will be added as nullable")
            return
        migrate()


if __name__ == "__main__":
    main()
