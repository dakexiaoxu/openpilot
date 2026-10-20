from opendbc.car.selected_car import get_selected_car_platform
from opendbc.car.volkswagen.values import CAR as VOLKSWAGEN


def test_volkswagen_jetta_mk7_aliases():
  expected = VOLKSWAGEN.VOLKSWAGEN_JETTA_MK7
  assert get_selected_car_platform("Volkswagen Jetta 2018-23") == expected
  assert get_selected_car_platform("Volkswagen Jetta GLI 2021-23") == expected
  assert get_selected_car_platform("VOLKSWAGEN_JETTA_MK7") == expected
  assert get_selected_car_platform(b"VOLKSWAGEN_JETTA_MK7") == expected
  assert get_selected_car_platform("MOCK") is None
