from django.db import migrations


SQL_CREATE_FAVORITE = r'''
CREATE TABLE IF NOT EXISTS barbers_favorite (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users_user(id) DEFERRABLE INITIALLY DEFERRED,
    barbershop_id BIGINT NOT NULL REFERENCES barbers_barbershop(id) DEFERRABLE INITIALLY DEFERRED,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS barbers_favorite_user_barbershop_uniq
    ON barbers_favorite (user_id, barbershop_id);
'''


class Migration(migrations.Migration):

    dependencies = [
        ('barbers', '0003_lastviewed'),
        ('users', '0002_useraddress_favorite_lastviewed'),
    ]

    operations = [
        migrations.RunSQL(SQL_CREATE_FAVORITE, migrations.RunSQL.noop),
    ]


