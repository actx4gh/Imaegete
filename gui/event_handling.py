import config
from glavnaqt.core.event_handling import handle_resize_event as glavnaqt_handle_resize_event
from glavnaqt.core.event_handling import setup_event_handling as glavnaqt_setup_event_handling


def setup_event_handling(main_window, resize_signal):
    logger.debug("Setting up event handling.")
    # Call glavnaqt's event handling setup
    glavnaqt_setup_event_handling(main_window, resize_signal)

    # Custom connections for image-sorter
    main_window.resize_signal.resized.connect(main_window.update_zoom_percentage)
    logger.debug("Connected resize signal to update_zoom_percentage.")

def handle_resize_event(main_window, event, update_status_bar):
    logger.debug(f"Handling resize event: {event}.")
    glavnaqt_handle_resize_event(main_window, event)

    if main_window.resize_timer.isActive():
        main_window.resize_timer.stop()
    main_window.resize_timer.start(config.RESIZE_TIMER_INTERVAL)
    logger.debug("Resize timer started.")
    main_window.log_resize_event()

    current_image_path = main_window.image_controller.image_manager.get_current_image_path()
    logger.debug(f"Current image path: {current_image_path}")
    if current_image_path:
        cached_metadata = main_window.image_controller.image_manager.image_cache.get_metadata(current_image_path)
        if cached_metadata:
            logger.debug(f"Using cached metadata: {cached_metadata}")
            main_window.update_zoom_percentage(cached_metadata['size'])
        else:
            logger.debug("No cached metadata found.")
            main_window.update_zoom_percentage()

    update_status_bar()
    logger.debug("Status bar updated after resize event.")

