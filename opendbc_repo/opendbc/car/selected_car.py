def get_selected_car_platform(name: str | bytes | None):
  from opendbc.car.ford.values import CAR as FORD
  from opendbc.car.hyundai.values import CAR as HYUNDAI
  from opendbc.car.gm.values import CAR as GM
  from opendbc.car.toyota.values import CAR as TOYOTA
  from opendbc.car.mazda.values import CAR as MAZDA
  from opendbc.car.volkswagen.values import CAR as VOLKSWAGEN
  from opendbc.car.tesla.values import CAR as TESLA

  if name is None:
    return None
  if isinstance(name, (bytes, bytearray)):
    name = name.decode("utf-8", errors="ignore")
  name = str(name).strip()
  if not name or name.upper() in ("MOCK", "NONE", "AUTO"):
    return None

  platforms = [platform for brand in (FORD, GM, TOYOTA, HYUNDAI, MAZDA, VOLKSWAGEN) for platform in brand]
  # Model X is intentionally dashcam-only. Model 3/Y have a CarController and
  # must be selectable even when automatic fingerprinting is unavailable.
  platforms.extend((TESLA.TESLA_MODEL_3, TESLA.TESLA_MODEL_Y))

  for platform in platforms:
    aliases = {platform.name, str(platform.value)}
    aliases.update(doc.name for doc in platform.config.car_docs)
    if name in aliases:
      return platform
  return None
