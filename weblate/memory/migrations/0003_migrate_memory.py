# Generated by Django 3.0.4 on 2020-03-09 13:04

from django.db import migrations
from whoosh.filedb.filestore import FileStorage
from whoosh.index import EmptyIndexError

from weblate.memory.utils import parse_category
from weblate.utils.data import data_dir


def is_invalid(model, obj_id, cache, method="get", **kwargs):
    if obj_id is not None:
        if obj_id not in cache:
            try:
                cache[obj_id] = getattr(model.objects, method)(**kwargs).id
            except (model.DoesNotExist, AttributeError):
                cache[obj_id] = None
        if cache[obj_id] is None:
            return True
    return False


def migrate_memory(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    Memory = apps.get_model("memory", "Memory")
    Project = apps.get_model("trans", "Project")
    User = apps.get_model("weblate_auth", "User")
    Language = apps.get_model("lang", "Language")

    storage = FileStorage(data_dir("memory"))
    try:
        index = storage.open_index()
    except EmptyIndexError:
        # Skip the migration if old translation memory does not exist
        return
    searcher = index.searcher()
    total = searcher.doc_count()
    users = {None: None}
    projects = {None: None}
    languages = {None: None}

    objects = {}

    for pos, entry in enumerate(searcher.documents()):
        # Indicate progress as this might take long
        if pos % 1000 == 0:
            print(
                "Converting translation memory {}/{} [{}%]".format(
                    pos + 1, total, (pos + 1) * 100 // total
                )
            )

        # Ignore source strings
        if entry["source_language"] == entry["target_language"]:
            continue

        # Convert languages
        if is_invalid(
            Language,
            entry["source_language"],
            languages,
            "fuzzy_get",
            code=entry["source_language"],
            strict=True,
        ):
            continue
        if is_invalid(
            Language,
            entry["target_language"],
            languages,
            "fuzzy_get",
            code=entry["target_language"],
            strict=True,
        ):
            continue

        # Convert category to new fields
        from_file, shared, project_id, user_id = parse_category(entry["category"])

        # Check project still exists
        if is_invalid(Project, project_id, projects, pk=project_id):
            continue

        # Check user still exists
        if is_invalid(User, user_id, users, pk=user_id):
            continue

        # Create new entry, ignoring duplicates
        key = (
            languages[entry["source_language"]],
            languages[entry["target_language"]],
            entry["source"],
            entry["target"],
            entry["origin"],
            users[user_id],
            projects[project_id],
            from_file,
            shared,
        )
        objects[key] = Memory(
            source_language_id=languages[entry["source_language"]],
            target_language_id=languages[entry["target_language"]],
            source=entry["source"],
            target=entry["target"],
            origin=entry["origin"],
            user_id=users[user_id],
            project_id=projects[project_id],
            from_file=from_file,
            shared=shared,
        )

    print("Inserting into the database...")
    Memory.objects.using(db_alias).bulk_create(objects.values())


class Migration(migrations.Migration):

    dependencies = [
        ("memory", "0002_memory"),
        ("lang", "0006_auto_20200309_1436"),
        ("weblate_auth", "0006_auto_20190905_1139"),
    ]

    operations = [
        migrations.RunPython(migrate_memory, migrations.RunPython.noop, elidable=True)
    ]
