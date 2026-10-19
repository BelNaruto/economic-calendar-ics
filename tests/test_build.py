from pathlib import Path

from icalendar import Calendar

from econcal_ics.build import main
from econcal_ics.client import load_events

SAMPLE = Path(__file__).with_name("sample-events.json")


def test_parse_sample():
    events = load_events(sample_file=SAMPLE)
    assert len(events) > 100
    cpi = next(e for e in events if e.title == "CPI (YoY) (Sep)" and e.country == "united states")
    assert cpi.when.hour == 12 and cpi.when.minute == 30
    assert cpi.surprise() == "beat"


def test_build_feeds(tmp_path):
    assert main(["--out", str(tmp_path), "--sample", str(SAMPLE)]) == 0
    ics = (tmp_path / "us-big-releases.ics").read_bytes()
    cal = Calendar.from_ical(ics)
    summaries = [str(c.get("summary")) for c in cal.walk("VEVENT")]
    assert any("Fed Interest Rate Decision" in s for s in summaries)
    assert any("Nonfarm Payrolls" in s for s in summaries)
    assert (tmp_path / "index.html").read_text().count("Google Calendar") >= 8
