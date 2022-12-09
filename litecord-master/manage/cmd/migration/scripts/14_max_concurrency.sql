alter table users
    add column max_concurrency int not null default 1
    check(bot = true or max_concurrency = 1);