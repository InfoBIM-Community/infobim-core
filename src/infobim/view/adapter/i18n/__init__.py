from __future__ import annotations

from typing import Tuple

from ontobdc.shared.adapter.i18n import (
    FullCatalog,
    I18nCatalogLoader,
    LocaleCatalog,
)

_LOADER: I18nCatalogLoader = I18nCatalogLoader(
    package_name="infobim",
    resource_path=("view", "adapter", "i18n", "locale"),
)

DEFAULT_LOCALE: str = I18nCatalogLoader.DEFAULT_LOCALE
SUPPORTED_LOCALES: Tuple[str, ...] = _LOADER.supported_locales


def full_catalog() -> FullCatalog:
    return _LOADER.full_catalog()


def catalog_for_namespace(namespace: str) -> LocaleCatalog:
    return _LOADER.catalog_for_namespace(namespace)
