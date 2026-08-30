def get_selected_car_platform(name: str):
  from opendbc.car.ford.values import CAR as FORD
  from opendbc.car.hyundai.values import CAR as HYUNDAI
  from opendbc.car.gm.values import CAR as GM
  from opendbc.car.toyota.values import CAR as TOYOTA
  from opendbc.car.mazda.values import CAR as MAZDA
  from opendbc.car.volkswagen.values import CAR as VOLKSWAGEN
  from opendbc.car.tesla.values import CAR as TESLA

  selected = str(name or "").strip()
  if not selected or "mock" in selected.lower():
    return None

  platforms = [platform for brand in (FORD, GM, TOYOTA, HYUNDAI, MAZDA, VOLKSWAGEN) for platform in brand]
  # Model X is intentionally dashcam-only. Model 3/Y have a CarController and
  # must be selectable even when automatic fingerprinting is unavailable.
  platforms.extend((TESLA.TESLA_MODEL_3, TESLA.TESLA_MODEL_Y))

  normalized = selected.replace(" ", "_").upper()
  for platform in platforms:
    aliases = {
      platform.name,
      platform.value,
      str(platform),
      platform.name.replace("_", " "),
    }
    aliases.update(doc.name for doc in platform.config.car_docs)
    if selected in aliases or normalized == platform.name.upper():
      return platform
    if platform.name in selected.upper().replace(" ", "_"):
      return platform

  return next((platform for platform in platforms for doc in platform.config.car_docs if selected == doc.name), None)
