class LoadDistribution:
    """
    Calculates rack loading for GB200 NVL72.
    """
    def __init__(self, rack_weight_kg: float):
        self.weight_kg = rack_weight_kg
        self.castors = 4

    def get_point_load(self) -> float:
        """Weight per castor in kg."""
        return self.weight_kg / self.castors

    def get_floor_pressure_kpa(self, area_sq_m: float) -> float:
        """Pressure in Kilopascals."""
        # Force = mass * gravity
        force_n = self.weight_kg * 9.81
        return (force_n / area_sq_m) / 1000.0
