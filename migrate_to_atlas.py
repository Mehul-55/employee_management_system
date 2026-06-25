"""
Copy Employee Management System data from local MongoDB to MongoDB Atlas.

Examples:
    python migrate_to_atlas.py --atlas-uri="mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"

Replace existing Atlas collections before copying:
    python migrate_to_atlas.py --atlas-uri="mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority" --drop
"""

import argparse
import os
import sys

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import BulkWriteError, PyMongoError


DEFAULT_LOCAL_URI = "mongodb://localhost:27017/"
DEFAULT_DB_NAME = "employee_attendance"
BATCH_SIZE = 500


def get_client(uri):
    return MongoClient(
        uri,
        serverSelectionTimeoutMS=8000,
        connectTimeoutMS=8000,
        appname="EmployeeManagementSystemMigration",
    )


def copy_indexes(source_collection, target_collection):
    for index in source_collection.list_indexes():
        index_name = index.get("name")
        if index_name == "_id_":
            continue

        keys = list(index["key"].items())
        options = {
            key: value
            for key, value in index.items()
            if key not in {"v", "key", "ns"}
        }
        target_collection.create_index(keys, **options)


def copy_collection(source_collection, target_collection):
    copied = 0
    batch = []

    for document in source_collection.find({}):
        batch.append(document)
        if len(batch) >= BATCH_SIZE:
            target_collection.insert_many(batch, ordered=False)
            copied += len(batch)
            batch = []

    if batch:
        target_collection.insert_many(batch, ordered=False)
        copied += len(batch)

    return copied


def migrate(local_uri, atlas_uri, db_name, drop_existing=False):
    local_client = get_client(local_uri)
    atlas_client = get_client(atlas_uri)

    local_client.admin.command("ping")
    atlas_client.admin.command("ping")

    source_db = local_client[db_name]
    target_db = atlas_client[db_name]
    collection_names = source_db.list_collection_names()

    if not collection_names:
        print(f"No collections found in local database '{db_name}'.")
        return 0

    print(f"Source: local MongoDB database '{db_name}'")
    print(f"Target: MongoDB Atlas database '{db_name}'")
    print(f"Collections found: {', '.join(collection_names)}")

    total_copied = 0
    for name in collection_names:
        source_collection = source_db[name]
        target_collection = target_db[name]

        if drop_existing:
            target_collection.drop()

        print(f"\nCopying collection: {name}")
        copied = copy_collection(source_collection, target_collection)
        copy_indexes(source_collection, target_collection)
        print(f"Copied {copied} documents.")
        total_copied += copied

    return total_copied


def main():
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Migrate local Employee Management System MongoDB data to Atlas."
    )
    parser.add_argument(
        "--local-uri",
        default=os.getenv("LOCAL_MONGO_URI", DEFAULT_LOCAL_URI),
        help="Local MongoDB URI. Default: mongodb://localhost:27017/",
    )
    parser.add_argument(
        "--atlas-uri",
        default=os.getenv("ATLAS_MONGO_URI"),
        help="MongoDB Atlas URI. Can also be set with ATLAS_MONGO_URI in .env.",
    )
    parser.add_argument(
        "--db-name",
        default=os.getenv("MONGO_DB_NAME", DEFAULT_DB_NAME),
        help="Database name to migrate. Default: employee_attendance",
    )
    parser.add_argument(
        "--drop",
        action="store_true",
        help="Drop matching Atlas collections before copying local data.",
    )
    args = parser.parse_args()

    if not args.atlas_uri:
        print("ERROR: Atlas URI is required. Pass --atlas-uri or set ATLAS_MONGO_URI in .env.")
        sys.exit(1)

    try:
        total = migrate(
            local_uri=args.local_uri,
            atlas_uri=args.atlas_uri,
            db_name=args.db_name,
            drop_existing=args.drop,
        )
    except BulkWriteError as exc:
        print("\nERROR: Some documents already exist in Atlas.")
        print("Run again with --drop if you want to replace Atlas data with local data.")
        print(exc.details.get("writeErrors", [{}])[0].get("errmsg", exc))
        sys.exit(1)
    except PyMongoError as exc:
        print(f"\nERROR: MongoDB migration failed: {exc}")
        sys.exit(1)

    print(f"\nMigration complete. Total documents copied: {total}")


if __name__ == "__main__":
    main()
