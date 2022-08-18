create table if not exists queued_url (
    id integer primary key autoincrement,
    url varchar not null,
    url_id integer not null,
    imported_data_id integer not null,
    category_id integer not null
);

create table if not exists raw_pages (
    id integer primary key autoincrement,
    url varchar not null,              -- queued_url.url_id
    url_id integer not null,           -- queued_url.url_id
    imported_data_id integer not null, -- queued_url.url_id
    category_id integer not null,      -- queued_url.url_id
    text clob not null,
    request_debug_info blob not null
);

create table if not exists load_failure (
    id integer primary key autoincrement,
    url_id integer not null,           -- queued_url.url_id
    http_code integer not null,
    error_string varchar not null
);
