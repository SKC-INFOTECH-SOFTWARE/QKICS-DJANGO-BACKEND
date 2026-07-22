from django.db import migrations


class Migration(migrations.Migration):
    """Add a MySQL/MariaDB FULLTEXT index on the post text columns so search can
    use MATCH ... AGAINST (index-backed) instead of slow LIKE '%q%' scans.

    Django doesn't model FULLTEXT indexes, so this is a raw ALTER TABLE. The
    query that uses it lives in community.views.SearchPostsView.
    """

    dependencies = [
        ("community", "0002_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=(
                "ALTER TABLE community_post "
                "ADD FULLTEXT INDEX post_fulltext_idx (title, content, full_content);"
            ),
            reverse_sql=(
                "ALTER TABLE community_post DROP INDEX post_fulltext_idx;"
            ),
        ),
    ]
