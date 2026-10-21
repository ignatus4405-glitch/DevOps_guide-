---
id: ansible-internals
title: Ansible изнутри: inventory, facts, handlers
minutes: 30
---

# Ansible изнутри: inventory, facts, handlers

Ansible кажется простым: YAML и SSH. Но порядок выполнения, факты и handlers
определяют, будет ли роль идемпотентной и предсказуемой.

## Inventory

Источник хостов: статический файл, динамический плагин, облако. Группы и
переменные наследуются по уровням:

```text
group_vars/all.yml
group_vars/web.yml
host_vars/web1.yml
```

Приоритет переменных — частая причина сюрпризов. Чем ближе к хосту, тем выше,
но `extra_vars` перебивает всё.

## Facts

Перед задачами Ansible собирает факты (`ansible_facts`): ОС, IP, память, диски.
Это позволяет писать условную логику:

```yaml
- name: установить пакет
  apt:
    name: nginx
  when: ansible_os_family == "Debian"
```

`gather_facts: false` ускоряет запуск, если факты не нужны.

## Порядок выполнения

Play выполняет задачи сверху вниз. `roles` раскрываются в `pre_tasks`,
`roles`, `tasks`, `post_tasks`. Handlers запускаются в конце, если были
уведомлены, и один раз.

Это значит: нельзя рассчитывать, что handler выполнится сразу после задачи.

## Идемпотентность

Модуль должен описывать состояние, а не действие:

- `copy`/`template` вместо `command`;
- `service: state=started` вместо `systemctl start`;
- `command` с `creates`/`changed_when`, если без него нельзя.

Проверка: второй прогон даёт `changed=0`.

## Handlers

```yaml
- name: конфиг nginx
  template: src=nginx.conf.j2 dest=/etc/nginx/nginx.conf
  notify: reload nginx
```

Handler сработает один раз даже при нескольких изменениях. `meta: flush_handlers`
форсирует выполнение в середине play.

## Стратегии и параллелизм

- `forks` — число параллельных хостов;
- `serial` — батчами (canary);
- `strategy: free` — каждый хост идёт своим темпом;
- `any_errors_fatal` — остановить всё при ошибке.

## Отладка

```bash
ansible-playbook -i inv site.yml --check --diff
ansible-playbook -i inv site.yml -vvv
ansible-inventory --list
ansible localhost -m setup
```

`--check` показывает изменения, `--diff` — содержимое. Не все модули
поддерживают check mode; это нужно учитывать.

## Как проверить себя

1. Зачем group_vars и host_vars?
2. Что такое facts?
3. Почему handlers выполняются в конце?
4. Как проверить идемпотентность?
5. Что делает `serial`?

!!! tip "Практика"
    Задача «Идемпотентная роль» в практикуме: добиться changed=0.

## Подробный разбор темы

Playbook проходит этапы: выбор hosts, сбор facts, обработка блоков и handlers, выполнение task по порядку. Facts полезны для условной конфигурации, но сбор их на каждом прогоне увеличивает время и требует корректного доступа к узлам; выключайте его только если роль действительно не зависит от facts. Inventory plugin может получать узлы динамически, поэтому результат нужно проверять перед массовым запуском.

Handlers запускаются по уведомлению и обычно исполняются в конце play; несколько уведомлений одного handler схлопываются в один запуск. Это предотвращает лишние перезапуски, но может удивить при ожидании немедленного применения. Используйте tags и `--limit` аккуратно, потому что избирательный запуск может пропустить подготовительный task. Включайте diff, но скрывайте секреты и персональные данные.

## Пошаговый сценарий

![Порядок действий: Ansible изнутри: inventory, facts, handlers](assets/img/howto/08-iac--09-ansible-internals.svg)

1. Проследите порядок inventory, variable precedence и host selection.
2. Проверьте privilege escalation и SSH-подключение без раскрытия ключей.
3. Запустите узкий playbook с verbosity, diff и контролируемым check mode.
4. Сверьте фактические изменения, handlers и повторный идемпотентный запуск.
