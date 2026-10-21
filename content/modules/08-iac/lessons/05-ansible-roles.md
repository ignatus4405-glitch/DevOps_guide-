---
id: ansible-roles
title: Ansible: роли, inventory, vault, идемпотентность
minutes: 30
---

# Ansible: роли, inventory, vault, идемпотентность

Ansible настраивает серверы без агентов: подключается по SSH и применяет задачи.
Главное свойство — идемпотентность: повторный запуск не должен ничего менять.

## Inventory

```ini
[web]
web-1 ansible_host=10.0.1.10
web-2 ansible_host=10.0.1.11

[db]
db-1 ansible_host=10.0.2.10

[all:vars]
ansible_user=ubuntu
ansible_ssh_private_key_file=~/.ssh/id_ed25519
```

Динамический inventory — для облака:

```bash
ansible-inventory -i inventory/aws_ec2.yml --graph
```

Плагин `amazon.aws.aws_ec2` сам находит инстансы по тегам. Это единственный
надёжный способ, когда серверы создаются и удаляются автоматически.

## Playbook и задачи

```yaml
- name: Настроить веб-серверы
  hosts: web
  become: true
  vars:
    app_port: 8080
  tasks:
    - name: Установить пакеты
      ansible.builtin.apt:
        name: [nginx, curl]
        state: present
        update_cache: true

    - name: Положить конфиг
      ansible.builtin.template:
        src: nginx.conf.j2
        dest: /etc/nginx/sites-available/app
        mode: "0644"
      notify: reload nginx

  handlers:
    - name: reload nginx
      ansible.builtin.service:
        name: nginx
        state: reloaded
```

Ключевые моменты:

- `state: present` идемпотентен; `command`/`shell` — нет, их используют только с
  `creates`/`changed_when`;
- `notify` запускает handler только при изменении;
- `template` использует Jinja2 и переменные.

## Роли: переиспользование

```
roles/
  app/
    tasks/main.yml
    handlers/main.yml
    templates/app.env.j2
    defaults/main.yml
    vars/main.yml
    meta/main.yml
```

```yaml
- hosts: web
  roles:
    - role: app
      vars:
        app_version: "1.4.2"
```

`defaults` переопределяются, `vars` — почти нет. Для переопределяемых значений —
всегда `defaults`.

Проверка:

```bash
ansible-galaxy init roles/app
ansible-lint
ansible-playbook site.yml --check --diff
```

`--check` — dry-run, `--diff` показывает изменения файлов. Это обязательная
комбинация перед prod.

## Ansible Vault

```bash
ansible-vault create secrets.yml
ansible-vault edit secrets.yml
ansible-vault encrypt_string 's3cr3t' --name 'db_password'
ansible-playbook site.yml --ask-vault-pass
ansible-playbook site.yml --vault-password-file ~/.vault_pass
```

Vault шифрует файл целиком или отдельные значения. Файл можно хранить в git, но
пароль — в менеджере секретов или CI.

Правила:

- отдельный vault-файл на окружение;
- пароль не в репозитории;
- ротация пароля vault при уходе сотрудника;
- `no_log: true` для задач с секретами, чтобы не попадали в вывод.

## Идемпотентность на практике

| Плохо | Хорошо |
| --- | --- |
| `shell: useradd app` | `user: name=app` |
| `shell: mkdir /srv/app` | `file: path=/srv/app state=directory` |
| `shell: systemctl restart app` | `service: name=app state=restarted` (только при изменении) |
| `shell: echo ... >> file` | `lineinfile`/`blockinfile` |

`shell` без `creates` выполняется каждый раз и всегда «changed», что ломает
отчёты и триггерит handlers.

## Проверка перед применением

```bash
ansible all -m ping
ansible-playbook site.yml --syntax-check
ansible-playbook site.yml --check --diff --limit web-1
ansible-playbook site.yml
```

`--limit` позволяет проверить на одном хосте. Это дешевле, чем чинить весь парк.

## Подробный разбор темы

Role упаковывает задачу конфигурации в предсказуемую структуру: defaults для изменяемых значений, tasks для действий, templates/files для артефактов, handlers для перезапуска после изменения. Inventory задаёт группы и переменные узлов; храните общие значения на уровне группы, специфичные — на уровне host только при необходимости.

`no_log` защищает чувствительный task output, но усложняет диагностику, поэтому секреты нужно минимизировать до передачи в task. Ansible Vault шифрует данные в репозитории, а внешний secret manager может выдавать динамические значения. Проверяйте роль на пустой и целевой конфигурации, выполняйте второй прогон и убедитесь, что handler запускается только при реальном изменении.

## Проверьте себя

1. Почему `shell` опасен для идемпотентности и что использовать вместо него?
2. Чем `defaults` отличается от `vars` в роли?
3. Что проверяет `--check --diff`?
4. Где хранить пароль Ansible Vault?

!!! tip "Практика"
    Задача «Роль Ansible» в практикуме: написать роль, которая идемпотентно
    ставит nginx и конфиг, с handler на reload.
