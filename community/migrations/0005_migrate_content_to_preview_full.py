from django.db import migrations


POST_PREVIEW_LENGTH = 1000
COMMENT_PREVIEW_LENGTH = 300


def migrate_post_content(apps, schema_editor):
    Post = apps.get_model("community", "Post")

    for post in Post.objects.all():
        # Skip if already migrated
        if post.preview_content and post.full_content:
            continue

        content = post.content or ""

        post.preview_content = content[:POST_PREVIEW_LENGTH]
        post.full_content = content
        post.save(update_fields=["preview_content", "full_content"])


def migrate_comment_content(apps, schema_editor):
    Comment = apps.get_model("community", "Comment")

    for comment in Comment.objects.all():
        # Skip if already migrated
        if comment.preview_content and comment.full_content:
            continue

        content = comment.content or ""

        comment.preview_content = content[:COMMENT_PREVIEW_LENGTH]
        comment.full_content = content
        comment.save(update_fields=["preview_content", "full_content"])


class Migration(migrations.Migration):

    dependencies = [
        ("community", "0004_comment_full_content_comment_preview_content_and_more"),
    ]

    operations = [
        migrations.RunPython(migrate_post_content),
        migrations.RunPython(migrate_comment_content),
    ]
