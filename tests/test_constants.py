from constants import lesson_time_str, LESSON_TIMES, LESSON_TIMES_DISPLAY


def test_lesson_time_str_valid():
    assert lesson_time_str(1) == '09:00-10:30'
    assert lesson_time_str(2) == '10:45-12:15'
    assert lesson_time_str(3) == '12:30-14:00'
    assert lesson_time_str(4) == '14:40-16:10'
    assert lesson_time_str(5) == '16:25-17:55'
    assert lesson_time_str(6) == '18:05-19:35'


def test_lesson_time_str_invalid():
    assert lesson_time_str(0) == ''
    assert lesson_time_str(7) == ''
    assert lesson_time_str(-1) == ''


def test_lesson_times_dict_matches_display():
    for num, (start, end) in LESSON_TIMES.items():
        assert LESSON_TIMES_DISPLAY[num] == f'{start}-{end}'


def test_lesson_times_display_first_empty():
    assert LESSON_TIMES_DISPLAY[0] == ''
