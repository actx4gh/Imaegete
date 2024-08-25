import config
from glavnaqt.core.event_handling import handle_resize_event as glavnaqt_handle_resize_event
from glavnaqt.core.event_handling import setup_event_handling as glavnaqt_setup_event_handling


def setup_event_handling(main_window, resize_signal):
    # Call glavnaqt's event handling setup
    glavnaqt_setup_event_handling(main_window, resize_signal)

    # Custom connections for image-sorter
    main_window.resize_signal.resized.connect(main_window.update_zoom_percentage)


def handle_resize_event(main_window, event, update_status_bar):
    glavnaqt_handle_resize_event(main_window, event)

    # Use cached thumbnail metadata to reduce load
    if main_window.resize_timer.isActive():
        main_window.resize_timer.stop()
    main_window.resize_timer.start(config.RESIZE_TIMER_INTERVAL)
    main_window.log_resize_event()

    # Efficiently update UI using cache
    current_image_path = main_window.image_controller.image_manager.get_current_image_path()
    if current_image_path:
        cached_metadata = main_window.image_controller.image_manager.image_cache.get_metadata(current_image_path)
        if cached_metadata:
            main_window.update_zoom_percentage(cached_metadata['size'])
        else:
            main_window.update_zoom_percentage()

    update_status_bar()
