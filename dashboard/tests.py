from datetime import date
from unittest import mock

import pytest

from dashboard.services import revenue_series

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("today", [date(2026, 11, 26), date(2026, 3, 31), date(2026, 1, 1)])
def test_revenue_series_ends_in_current_month(owner, today):
    with mock.patch("dashboard.services.timezone.localdate", return_value=today):
        s = revenue_series(owner)
    assert len(s["labels"]) == 12
    assert s["labels"][-1] == today.strftime("%b %y")
