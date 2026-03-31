import importlib
import json
import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ALUKINTERLAB.settings")

# Корень проекта (файл лежит в корне рядом с manage.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Имя битого файла можно переопределить: RESCUE_BROKEN_SQLITE=db.sqlite3.broken или абсолютный путь
_broken_relpath = os.environ.get("RESCUE_BROKEN_SQLITE", "db.sqlite3.broken")
_broken_name = (
    _broken_relpath
    if os.path.isabs(_broken_relpath)
    else os.path.join(BASE_DIR, _broken_relpath)
)

# DATABASES для экстрактора — только если файл существует, иначе остаётся БД из settings
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": _broken_name,
    },
}

_settings_mod = importlib.import_module(os.environ["DJANGO_SETTINGS_MODULE"])
if os.path.isfile(DATABASES["default"]["NAME"]):
    _settings_mod.DATABASES["default"] = DATABASES["default"]
    print(f"[rescue] Источник (битая БД): {DATABASES['default']['NAME']}")
else:
    print(
        f"[rescue] Битая БД не найдена ({DATABASES['default']['NAME']!r}) — "
        "ORM использует DATABASE из settings."
    )

django.setup()

from django.apps import apps  # noqa: E402


def rescue_model(model_label):
    Model = apps.get_model(model_label)
    data = []
    print(f"--- Спасаем {model_label} ---")
    try:
        # Пытаемся вытащить все объекты по одному
        for obj in Model.objects.all():
            try:
                # Превращаем объект в словарь (упрощенно)
                item = {
                    "model": model_label,
                    "pk": obj.pk,
                    "fields": {
                        field.name: getattr(obj, field.name)
                        for field in obj._meta.fields
                        if field.name != "id"
                    },
                }
                # Обработка простых типов для JSON
                for k, v in item["fields"].items():
                    if hasattr(v, "id"):
                        item["fields"][k] = v.id  # ForeignKey
                data.append(item)
            except Exception as e:
                print(
                    f" Пропущена битая запись в {model_label} "
                    f"(ID: {getattr(obj, 'pk', 'unknown')}): {e}"
                )

        if data:
            filename = f"rescued_{model_label.replace('.', '_')}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4, default=str)
            print(f" Успех! Сохранено {len(data)} записей в {filename}")
    except Exception as e:
        print(f" Ошибка доступа к таблице {model_label}: {e}")


# Все модели из зарегистрированных приложений (включая промежуточные M2M)
models_to_rescue = sorted(
    f"{model._meta.app_label}.{model._meta.object_name}"
    for model in apps.get_models(include_auto_created=True)
)

for m in models_to_rescue:
    rescue_model(m)
