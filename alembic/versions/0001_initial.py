"""Initial migration – creates all tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stories",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("premise", sa.Text, nullable=False),
        sa.Column("genre", sa.String(200), nullable=True),
        sa.Column("tone", sa.String(200), nullable=True),
        sa.Column("status", sa.String(50), nullable=False, default="created"),
        sa.Column("current_episode", sa.Integer, nullable=False, default=0),
        sa.Column("total_planned", sa.Integer, nullable=False, default=200),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_stories_status", "stories", ["status"])

    op.create_table(
        "story_plans",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("approved", sa.Boolean, default=False),
        sa.Column("arc_structure", JSONB, default=dict),
        sa.Column("episode_plans", JSONB, default=list),
        sa.Column("world_rules", JSONB, default=list),
        sa.Column("major_turning_points", JSONB, default=list),
        sa.Column("planned_resolutions", JSONB, default=list),
        sa.Column("version", sa.Integer, default=1),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("story_id", name="uq_story_plan"),
    )

    op.create_table(
        "episodes",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_number", sa.Integer, nullable=False),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("content", sa.Text, nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("hook", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), nullable=False, default="planned"),
        sa.Column("word_count", sa.Integer, nullable=True),
        sa.Column("revision_count", sa.Integer, default=0),
        sa.Column("characters_present", JSONB, default=list),
        sa.Column("facts_introduced", JSONB, default=list),
        sa.Column("threads_opened", JSONB, default=list),
        sa.Column("threads_resolved", JSONB, default=list),
        sa.Column("critic_score", sa.Float, nullable=True),
        sa.Column("critic_issues", JSONB, default=list),
        sa.Column("critic_passed", sa.Boolean, nullable=True),
        sa.Column("human_edited", sa.Boolean, default=False),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("edit_notes", sa.Text, nullable=True),
        sa.Column("is_stale", sa.Boolean, default=False),
        sa.Column("stale_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("story_id", "episode_number", name="uq_story_episode"),
    )
    op.create_index("ix_episodes_story_number", "episodes", ["story_id", "episode_number"])
    op.create_index("ix_episodes_status", "episodes", ["status"])

    op.create_table(
        "characters",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("role", sa.String(100), nullable=True),
        sa.Column("personality", sa.Text, nullable=True),
        sa.Column("goals", JSONB, default=list),
        sa.Column("relationships", JSONB, default=dict),
        sa.Column("current_state", sa.Text, nullable=True),
        sa.Column("important_facts", JSONB, default=list),
        sa.Column("character_arc", sa.Text, nullable=True),
        sa.Column("status", sa.String(50), default="alive"),
        sa.Column("first_appeared", sa.Integer, nullable=True),
        sa.Column("last_updated_episode", sa.Integer, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("story_id", "name", name="uq_story_character"),
    )
    op.create_index("ix_characters_story", "characters", ["story_id"])

    op.create_table(
        "world_facts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("key", sa.String(300), nullable=False),
        sa.Column("value", sa.Text, nullable=False),
        sa.Column("episode_introduced", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_world_facts_story_category", "world_facts", ["story_id", "category"])

    op.create_table(
        "open_threads",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("thread_type", sa.String(50), default="other"),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("episode_introduced", sa.Integer, nullable=False),
        sa.Column("episode_resolved", sa.Integer, nullable=True),
        sa.Column("planned_resolution", sa.Text, nullable=True),
        sa.Column("planned_resolution_episode", sa.Integer, nullable=True),
        sa.Column("status", sa.String(50), default="open"),
        sa.Column("importance", sa.String(20), default="medium"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_open_threads_story_status", "open_threads", ["story_id", "status"])

    op.create_table(
        "human_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_id", sa.String(36), sa.ForeignKey("episodes.id", ondelete="SET NULL"), nullable=True),
        sa.Column("after_episode", sa.Integer, nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("instruction", sa.Text, nullable=True),
        sa.Column("edited_content", sa.Text, nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_human_feedback_story_active", "human_feedback", ["story_id", "is_active"])

    op.create_table(
        "memory_summaries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary_type", sa.String(50), nullable=False),
        sa.Column("episode_start", sa.Integer, nullable=True),
        sa.Column("episode_end", sa.Integer, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_memory_summaries_story_type", "memory_summaries", ["story_id", "summary_type"])

    op.create_table(
        "agent_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("run_id", sa.String(36), nullable=False),
        sa.Column("story_id", sa.String(36), sa.ForeignKey("stories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("episode_number", sa.Integer, nullable=True),
        sa.Column("agent", sa.String(100), nullable=False),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("status", sa.String(50), default="success"),
        sa.Column("input_tokens", sa.Integer, nullable=True),
        sa.Column("output_tokens", sa.Integer, nullable=True),
        sa.Column("cost", sa.Float, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("retry_count", sa.Integer, default=0),
        sa.Column("decision", sa.String(100), nullable=True),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column("extra", JSONB, default=dict),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_runs_story_episode", "agent_runs", ["story_id", "episode_number"])
    op.create_index("ix_agent_runs_run_id", "agent_runs", ["run_id"])


def downgrade() -> None:
    op.drop_table("agent_runs")
    op.drop_table("memory_summaries")
    op.drop_table("human_feedback")
    op.drop_table("open_threads")
    op.drop_table("world_facts")
    op.drop_table("characters")
    op.drop_table("episodes")
    op.drop_table("story_plans")
    op.drop_table("stories")
