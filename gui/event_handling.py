from PyQt6.QtCore import QTimer

def setup_event_handling(main_window, resize_signal):
    main_window.resize_signal = resize_signal
    main_window.resize_signal.resized.connect(main_window.on_resize_timeout)

    main_window.resize_timer = QTimer()
    main_window.resize_timer.setSingleShot(True)
    main_window.resize_timer.timeout.connect(main_window.log_resize_event)
    main_window.resize_signal.resized.connect(main_window.update_zoom_percentage)

def handle_resize_event(main_window, event, update_status_bar):
    main_window.resize_signal.resized.emit()
    if main_window.resize_timer.isActive():
        main_window.resize_timer.stop()
    main_window.resize_timer.start(300)
    update_status_bar()
