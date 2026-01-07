"""
Tests for boards app models (Board, BoardColumn, BoardCard, etc.).
"""

import pytest
from django.utils import timezone
from datetime import timedelta

from apps.boards.models import (
    Board, BoardColumn, BoardCard, BoardCardLink, BoardCardAttachment,
    BoardCardLabel, BoardCardLabelAssignment, AutomationRule, AutomationAction,
    CardButton, CardButtonAction
)


class TestBoard:
    """Test cases for Board model."""

    def test_create_board(self, organization_factory, user_factory):
        """Test creating a basic board."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(
            organization=org,
            title="Test Board",
            created_by=user
        )

        assert board.title == "Test Board"
        assert board.organization == org
        assert board.created_by == user
        assert str(board) == "Test Board"

    def test_board_str_representation(self, organization_factory, user_factory):
        """Test string representation of board."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(
            organization=org,
            title="Kanban Board",
            created_by=user
        )

        assert str(board) == "Kanban Board"


class TestBoardColumn:
    """Test cases for BoardColumn model."""

    def test_create_board_column(self, organization_factory, user_factory):
        """Test creating a board column."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(
            organization=org,
            title="Test Board",
            created_by=user
        )

        column = BoardColumn.objects.create(
            board=board,
            title="To Do",
            sort_order=1
        )

        assert column.board == board
        assert column.title == "To Do"
        assert column.sort_order == 1
        assert str(column) == f"{board.title}: {column.title}"

    def test_column_ordering(self, organization_factory, user_factory):
        """Test that columns are ordered by sort_order."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(
            organization=org,
            title="Test Board",
            created_by=user
        )

        col1 = BoardColumn.objects.create(board=board, title="Col 1", sort_order=2)
        col2 = BoardColumn.objects.create(board=board, title="Col 2", sort_order=1)
        col3 = BoardColumn.objects.create(board=board, title="Col 3", sort_order=3)

        columns = list(BoardColumn.objects.filter(board=board))
        assert columns[0] == col2  # sort_order=1
        assert columns[1] == col1  # sort_order=2
        assert columns[2] == col3  # sort_order=3


class TestBoardCard:
    """Test cases for BoardCard model."""

    def test_create_board_card(self, organization_factory, user_factory):
        """Test creating a board card."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(
            organization=org,
            title="Test Board",
            created_by=user
        )

        column = BoardColumn.objects.create(
            board=board,
            title="To Do",
            sort_order=1
        )

        card = BoardCard.objects.create(
            column=column,
            title="Test Card",
            description="Card description",
            created_by=user
        )

        assert card.column == column
        assert card.title == "Test Card"
        assert card.description == "Card description"
        assert card.created_by == user
        assert card.sort_order == 0
        assert str(card) == "Test Card"

    def test_card_ordering(self, organization_factory, user_factory):
        """Test that cards are ordered by sort_order."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)
        column = BoardColumn.objects.create(board=board, title="To Do", sort_order=1)

        card1 = BoardCard.objects.create(column=column, title="Card 1", sort_order=2, created_by=user)
        card2 = BoardCard.objects.create(column=column, title="Card 2", sort_order=1, created_by=user)
        card3 = BoardCard.objects.create(column=column, title="Card 3", sort_order=3, created_by=user)

        cards = list(BoardCard.objects.filter(column=column))
        assert cards[0] == card2  # sort_order=1
        assert cards[1] == card1  # sort_order=2
        assert cards[2] == card3  # sort_order=3


class TestBoardCardLink:
    """Test cases for BoardCardLink model."""

    def test_create_card_link(self, organization_factory, user_factory):
        """Test creating a card link."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)
        column = BoardColumn.objects.create(board=board, title="To Do", sort_order=1)
        card = BoardCard.objects.create(column=column, title="Test Card", created_by=user)

        link = BoardCardLink.objects.create(
            card=card,
            title="Related Issue",
            url="https://github.com/org/repo/issues/123"
        )

        assert link.card == card
        assert link.title == "Related Issue"
        assert link.url == "https://github.com/org/repo/issues/123"
        assert str(link) == "https://github.com/org/repo/issues/123"


class TestBoardCardLabel:
    """Test cases for BoardCardLabel model."""

    def test_create_card_label(self, organization_factory, user_factory):
        """Test creating a card label."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)

        label = BoardCardLabel.objects.create(
            board=board,
            name="Bug",
            color="red"
        )

        assert label.board == board
        assert label.name == "Bug"
        assert label.color == "red"
        assert str(label) == "Bug"

    def test_label_unique_per_board(self, organization_factory, user_factory):
        """Test that labels must be unique per board."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)

        BoardCardLabel.objects.create(board=board, name="Duplicate", color="blue")

        # Creating duplicate should fail
        with pytest.raises(Exception):  # IntegrityError
            BoardCardLabel.objects.create(board=board, name="Duplicate", color="red")

        # But different board can have same name
        board2 = Board.objects.create(organization=org, title="Board 2", created_by=user)
        BoardCardLabel.objects.create(board=board2, name="Duplicate", color="green")  # Should not raise


class TestAutomationRule:
    """Test cases for AutomationRule model."""

    def test_create_automation_rule(self, organization_factory, user_factory):
        """Test creating an automation rule."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)

        rule = AutomationRule.objects.create(
            board=board,
            name="Auto-move completed cards",
            trigger_type=AutomationRule.TriggerType.CARD_MOVED,
            trigger_config={"from_column_id": "todo", "to_column_id": "done"},
            is_active=True,
            created_by=user
        )

        assert rule.board == board
        assert rule.name == "Auto-move completed cards"
        assert rule.trigger_type == AutomationRule.TriggerType.CARD_MOVED
        assert rule.is_active is True
        assert str(rule) == "Auto-move completed cards (Card Moved)"

    def test_rule_ordering(self, organization_factory, user_factory):
        """Test that rules are ordered by created_at desc."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)

        rule1 = AutomationRule.objects.create(board=board, name="Rule 1", trigger_type=AutomationRule.TriggerType.CARD_CREATED, created_by=user)
        rule2 = AutomationRule.objects.create(board=board, name="Rule 2", trigger_type=AutomationRule.TriggerType.CARD_CREATED, created_by=user)
        rule3 = AutomationRule.objects.create(board=board, name="Rule 3", trigger_type=AutomationRule.TriggerType.CARD_CREATED, created_by=user)

        rules = list(AutomationRule.objects.filter(board=board))
        assert rules[0] == rule3  # Most recent first
        assert rules[1] == rule2
        assert rules[2] == rule1


class TestCardButton:
    """Test cases for CardButton model."""

    def test_create_card_button(self, organization_factory, user_factory):
        """Test creating a card button."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)

        button = CardButton.objects.create(
            board=board,
            name="Mark as Urgent",
            icon="exclamation",
            color="red",
            is_active=True,
            created_by=user
        )

        assert button.board == board
        assert button.name == "Mark as Urgent"
        assert button.icon == "exclamation"
        assert button.color == "red"
        assert button.is_active is True
        assert str(button) == "Mark as Urgent"

    def test_button_should_show_for_card(self, organization_factory, user_factory):
        """Test the should_show_for_card method."""
        org = organization_factory()
        user = user_factory()

        board = Board.objects.create(organization=org, title="Test Board", created_by=user)
        column = BoardColumn.objects.create(board=board, title="To Do", sort_order=1)
        card = BoardCard.objects.create(column=column, title="Test Card", created_by=user)

        # Create a label for testing
        label = BoardCardLabel.objects.create(board=board, name="Urgent", color="red")

        # Button with required label
        label_button = CardButton.objects.create(
            board=board,
            name="Label Button",
            show_when_has_label=label,
            created_by=user
        )

        # Should not show without label
        assert label_button.should_show_for_card(card) is False

        # Add label to card
        BoardCardLabelAssignment.objects.create(card=card, label=label)
        assert label_button.should_show_for_card(card) is True

        # Button with hidden label
        hidden_button = CardButton.objects.create(
            board=board,
            name="Hidden Button",
            hide_when_has_label=label,
            created_by=user
        )

        # Should show without label
        card2 = BoardCard.objects.create(column=column, title="Card 2", created_by=user)
        assert hidden_button.should_show_for_card(card2) is True

        # Should not show with label
