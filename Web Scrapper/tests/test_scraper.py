"""tests/test_scraper.py"""
import pytest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone
import scraper

@patch('scraper.sys.exit', side_effect=SystemExit)
@patch('scraper.CONFIG_PATH')
def test_load_config_exits(mock_config_path, mock_exit):
    mock_config_path.exists.return_value = False
    with pytest.raises(SystemExit):
        scraper.load_config()
    mock_exit.assert_called_once_with(1)

@patch('scraper.importlib.import_module')
@patch('scraper.SleepPrevention')
@patch('scraper.CycleDatabase')
@patch('scraper.CloudTransport')
@patch('scraper.EmailNotifier')
@patch('scraper.UTCScheduler')
@patch('scraper.load_config')
def test_scraper_main_loop(
    mock_load_config, mock_scheduler_cls, mock_notifier_cls, 
    mock_transport_cls, mock_cycledb_cls, mock_sleep, mock_import
):
    mock_load_config.return_value = {
        "scrape_intervals_utc": ["00:00", "12:00"],
        "retailers": [
            {
                "retailer_id": "dummy",
                "enabled": True,
                "payload_module": "payload.dummy"
            },
            {
                "retailer_id": "broken",
                "enabled": True,
                "payload_module": "payload.broken"
            }
        ],
        "database": {"cycle_db_dir": "./data/cycles"}
    }
    
    mock_scheduler = MagicMock()
    mock_scheduler_cls.return_value = mock_scheduler
    
    # Capture on_cycle and fire it
    def side_effect_run(on_cycle):
        on_cycle(False, datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc))
        
    mock_scheduler.run.side_effect = side_effect_run
    
    mock_db = MagicMock()
    mock_cycledb_cls.return_value.__enter__.return_value = mock_db
    mock_db.get_all_records.return_value = [{"fake": "record"}]
    mock_db.insert_records.return_value = (1, 0)
    
    mock_transport = mock_transport_cls.return_value
    mock_notifier = mock_notifier_cls.return_value
    
    # Make import_module succeed for dummy, fail for broken
    mock_dummy_module = MagicMock()
    mock_dummy_scraper = MagicMock()
    mock_dummy_scraper.run.return_value = [{"fake": "record"}]
    mock_dummy_module.Scraper.return_value = mock_dummy_scraper
    
    def import_side_effect(name):
        if name == "payload.dummy":
            return mock_dummy_module
        else:
            raise ImportError("Cannot find module")
            
    mock_import.side_effect = import_side_effect
    
    # Evaluate
    scraper.main()
    
    mock_transport.flush_buffer.assert_called_once()
    mock_db.insert_records.assert_called_once_with([{"fake": "record"}])
    mock_notifier.notify_scrape_failure.assert_called_once_with("broken", "Cannot find module")
    mock_transport.upload_cycle_data.assert_called_once_with(
        [{"fake": "record"}], mock_db.cycle_id, "2026-04-05T12-00-00Z"
    )
    mock_notifier.notify_cycle_complete.assert_called_once()
