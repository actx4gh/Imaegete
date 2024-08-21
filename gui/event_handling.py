from glavnaqt.core.event_handling import setup_event_handling as glavnaqt_setup_event_handling
from glavnaqt.core.event_handling import handle_resize_event as glavnaqt_handle_resize_event


def setup_event_handling(main_window, resize_signal):
    # Call glavnaqt's event handling setup
    glavnaqt_setup_event_handling(main_window, resize_signal)

    # Custom connections for image-sorter
    main_window.resize_signal.resized.connect(main_window.update_zoom_percentage)


def handle_resize_event(main_window, event, update_status_bar):
    # Use glavnaqt's resize event handling
    glavnaqt_handle_resize_event(main_window, event)

    # Additional handling for image-sorter specific needs
    if main_window.resize_timer.isActive():
        main_window.resize_timer.stop()
    main_window.resize_timer.start(300)
    main_window.log_resize_event()

    # Update status bar
    update_status_bar()
