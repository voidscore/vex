# vex

**vex** — это инструмент для автоматической генерации версии проекта  
(C/C++ / make / cmake) на основе Git и упрощённой модели Semantic Versioning.

---

## Идея

vex решает проблему отсутствия дисциплины в версиях:

- версия увеличивается автоматически при git merge в main
- тип изменения определяется по commit message
- генерируется version.h для использования в коде
- поддерживается локальная разработка без CI

---

## Установка

    pipx install -e .
    pipx ensurepath

## Удаление

    pipx uninstall vex

---

## Быстрый старт

    vex init

---

## Команды

    vex init  
    vex sync --build  
    vex sync --git-commit-msg  
    vex sync --git-post-merge  

---

## Версионирование

    feat!  -> MAJOR  
    feat   -> MINOR  
    fix    -> PATCH  
    perf   -> PATCH  
    refactor -> PATCH  

---

## Структура

    .vex/state.json  
    version.json  
    generated/version.h