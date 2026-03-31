import os
from collections import deque

import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "ALUKINTERLAB.settings")
django.setup()

from django.apps import apps  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db.models import CharField, ForeignKey, OneToOneField  # noqa: E402
from django.db.models.signals import (  # noqa: E402
    m2m_changed,
    post_save,
    pre_save,
)


def disable_all_signals():
    """Глушим глобальные приёмники (SEO и прочее не дергаются при восстановлении)."""
    print("Отключение сигналов...")
    # post_save / pre_save / m2m_changed — общие на проект; достаточно очистить один раз каждый
    post_save.receivers = []
    pre_save.receivers = []
    m2m_changed.receivers = []


disable_all_signals()
User = get_user_model()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def _label_from_rescued_stem(stem: str):
    """rescued_home_RabotaMedia -> home.RabotaMedia (как при дампе в rescue_script)."""
    prefix = "rescued_"
    if not stem.startswith(prefix):
        return None
    rest = stem[len(prefix) :]
    for ac in sorted(apps.get_app_configs(), key=lambda c: len(c.label), reverse=True):
        lab = ac.label
        if rest.startswith(lab + "_"):
            model_part = rest[len(lab) + 1 :]
            if not model_part:
                continue
            try:
                apps.get_model(lab, model_part)
            except LookupError:
                continue
            return f"{lab}.{model_part}"
    return None


def discover_rescued_json(base_dir):
    """Метка модели -> абсолютный путь к JSON."""
    found = {}
    try:
        names = os.listdir(base_dir)
    except OSError:
        return found
    for name in names:
        if not name.startswith("rescued_") or not name.endswith(".json"):
            continue
        stem, _ = os.path.splitext(name)
        label = _label_from_rescued_stem(stem)
        if label:
            found[label] = os.path.join(base_dir, name)
    return found


def order_restore_labels(labels: set):
    """Топологический порядок: сначала то, на что ссылаются FK из набора, затем зависимые."""
    subgraph = set(labels)
    indegree = {L: 0 for L in subgraph}
    adj = {L: [] for L in subgraph}

    for L in list(subgraph):
        try:
            Model = apps.get_model(L)
        except LookupError:
            continue
        for f in Model._meta.fields:
            if isinstance(f, (ForeignKey, OneToOneField)):
                rel = f.remote_field.model
                if rel is None:
                    continue
                dep = f"{rel._meta.app_label}.{rel._meta.object_name}"
                if dep == L or dep not in subgraph:
                    continue
                adj[dep].append(L)
                indegree[L] += 1

    q = deque(sorted(L for L in subgraph if indegree[L] == 0))
    order = []
    while q:
        u = q.popleft()
        order.append(u)
        for dst in sorted(adj[u]):
            indegree[dst] -= 1
            if indegree[dst] == 0:
                q.append(dst)

    rest = sorted(L for L in subgraph if L not in order)
    return order + rest


def missing_required_fk_parents(model_label, rescued_map):
    """
    Если у модели есть NOT NULL FK на другую модель, а файла дампа для неё нет
    (как home.CartItem без rescued_home_Cart из-за malformed), восстановление обычно бессмысленно.
    Возвращает (имя_поля, dep_label) или None.
    """
    try:
        Model = apps.get_model(model_label)
    except LookupError:
        return None
    for f in Model._meta.fields:
        if not isinstance(f, (ForeignKey, OneToOneField)):
            continue
        if f.null:
            continue
        rel = f.remote_field.model
        if rel is None:
            continue
        dep = f"{rel._meta.app_label}.{rel._meta.object_name}"
        if dep == model_label:
            continue  # self-FK / дерево — pass 2
        if dep not in rescued_map:
            return f.name, dep
    return None


def restore_model(model_label, filename):
    if not os.path.exists(filename):
        print(f"Файл {filename} не найден.")
        return

    Model = apps.get_model(model_label)
    with open(filename, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n--- Восстанавливаем {model_label} ({len(data)} записей) ---")

    if model_label == "Blog.Post":
        u_ids = {
            item["fields"].get("author")
            for item in data
            if item["fields"].get("author")
        }
        for uid in u_ids:
            User.objects.get_or_create(
                pk=uid,
                defaults={"username": f"user_{uid}", "is_active": False},
            )

    # ПЕРВЫЙ ПРОХОД: скелет; для реальных FK/O2O пишем в attname (…_id), без проверки «должен быть instance»
    for item in data:
        fields = item["fields"]
        pk = item["pk"]
        clean_fields = {}

        for k, v in fields.items():
            if k == "parent":
                continue

            try:
                fld = Model._meta.get_field(k)
            except Exception:
                fld = None

            if isinstance(fld, (ForeignKey, OneToOneField)) and fld.name == k:
                clean_fields[fld.attname] = v
                continue

            if k.endswith("_id"):
                base = k[:-3]
                try:
                    fld_id = Model._meta.get_field(base)
                except Exception:
                    fld_id = None
                if isinstance(fld_id, (ForeignKey, OneToOneField)) and fld_id.attname == k:
                    clean_fields[k] = v
                    continue

            if k == "priority" and isinstance(v, str):
                clean_fields[k] = 0
                continue

            if k in ("tree_id", "lft", "rght", "level") and (v is None or v == ""):
                clean_fields[k] = 1
                continue

            clean_fields[k] = v

        # Обязательные CharField без NULL: в дампе часто null/"" (как у битых AssistantKnowledge)
        for field in Model._meta.local_concrete_fields:
            if not isinstance(field, CharField) or field.null:
                continue
            name = field.name
            val = clean_fields.get(name)
            if val is None or (val == "" and not field.blank):
                if field.choices:
                    clean_fields[name] = field.choices[0][0]
                elif field.has_default():
                    clean_fields[name] = field.get_default()
                else:
                    clean_fields[name] = "-"

        try:
            Model.objects.update_or_create(pk=pk, defaults=clean_fields)
        except Exception as e:
            print(f" Ошибка (Pass 1) PK {pk}: {e}")

    print(f" Проставляем связи для {model_label}...")
    for item in data:
        pk = item["pk"]
        parent_id = item["fields"].get("parent")
        if parent_id:
            try:
                Model.objects.filter(pk=pk).update(parent_id=parent_id)
            except Exception as e:
                print(f" Ошибка (Pass 2) PK {pk}: {e}")
    print(" Завершено.")


rescued_map = discover_rescued_json(BASE_DIR)
if not rescued_map:
    print(f"[restore] В {BASE_DIR!r} нет подходящих файлов rescued_*.json.")
else:
    load_order = order_restore_labels(set(rescued_map))
    print(
        f"\n[restore] Файлов: {len(rescued_map)}; порядок по FK "
        f"(первые 12): {', '.join(load_order[:12])}{'…' if len(load_order) > 12 else ''}"
    )
    allow_orphans = os.environ.get("RESTORE_ALLOW_ORPHANS", "").lower() in (
        "1",
        "true",
        "yes",
    )
    if allow_orphans:
        print(
            "[restore] RESTORE_ALLOW_ORPHANS: загрузка «сирот» с NOT NULL FK без дампа родителя."
        )
    for model_label in load_order:
        path = rescued_map.get(model_label)
        if not path:
            continue
        if not allow_orphans:
            miss = missing_required_fk_parents(model_label, rescued_map)
            if miss:
                fname, dep = miss
                print(
                    f"[restore] Пропуск {model_label}: NOT NULL FK «{fname}» -> {dep}, "
                    f"нет rescued_* для {dep}."
                )
                continue
        try:
            restore_model(model_label, path)
        except Exception as e:
            print(f"[restore] Ошибка при восстановлении {model_label}: {e}")

print("\nПересборка деревьев MPTT (если есть)...")
for _model in apps.get_models():
    mgr = _model._default_manager
    if hasattr(mgr, "rebuild"):
        try:
            mgr.rebuild()
            print(f" OK {_model._meta.label}")
        except Exception as e:
            print(f" Пропуск {_model._meta.label}: {e}")
