"""Finnish passport photo specification.

Source: https://lupakuvienvastaanotto.fi (kuvan_mitat_597.png).
Photo 36x47 mm = 500x653 px @ ~350 DPI.

Vertical layout (from top of photo):
    0 mm: photo top
    4 mm: upper crown line  ┐
                            │ crown band (2 mm)
    6 mm: lower crown line  ┘
    38 mm: upper chin line  ┐
                            │ chin band (2 mm)
    40 mm: lower chin line  ┘
    47 mm: photo bottom

Head height ranges:
    min head = lower crown -> upper chin = 32 mm
    max head = upper crown -> lower chin = 36 mm

Horizontal layout:
    Center band: 3 mm wide, centered. Face vertical center must fall here.
    Red horizontal guide lines are 16.5 mm wide, centered.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class PassportSpec:
    name: str
    photo_w_mm: float
    photo_h_mm: float

    # vertical
    top_gap_mm: float            # photo top to upper crown line
    crown_band_mm: float         # crown band thickness
    head_zone_mm: float          # lower crown to upper chin (= head_min)
    chin_band_mm: float          # chin band thickness
    # bottom_gap is computed: photo_h - top_gap - crown_band - head_zone - chin_band

    # horizontal
    h_line_width_mm: float       # length of red horizontal guides
    center_band_mm: float        # width of vertical center band
    horizontal_tolerance_mm: float  # max allowed face-center deviation

    @property
    def head_min_mm(self) -> float:
        return self.head_zone_mm  # lower crown -> upper chin

    @property
    def head_max_mm(self) -> float:
        return self.crown_band_mm + self.head_zone_mm + self.chin_band_mm

    @property
    def head_target_mm(self) -> float:
        return (self.head_min_mm + self.head_max_mm) / 2

    @property
    def upper_crown_y_mm(self) -> float:
        return self.top_gap_mm

    @property
    def lower_crown_y_mm(self) -> float:
        return self.top_gap_mm + self.crown_band_mm

    @property
    def upper_chin_y_mm(self) -> float:
        return self.lower_crown_y_mm + self.head_zone_mm

    @property
    def lower_chin_y_mm(self) -> float:
        return self.upper_chin_y_mm + self.chin_band_mm

    @property
    def bottom_gap_mm(self) -> float:
        return self.photo_h_mm - self.lower_chin_y_mm

    def head_target_ratio(self) -> float:
        return self.head_target_mm / self.photo_h_mm

    def head_min_ratio(self) -> float:
        return self.head_min_mm / self.photo_h_mm

    def head_max_ratio(self) -> float:
        return self.head_max_mm / self.photo_h_mm

    def top_gap_target_ratio(self) -> float:
        """Where the upper crown line sits — what auto-fit aims the hair-top
        for; auto-fit places top of hair midway in the crown band."""
        return (self.top_gap_mm + self.crown_band_mm / 2) / self.photo_h_mm


FINNISH = PassportSpec(
    name="Finnish",
    photo_w_mm=36.0,
    photo_h_mm=47.0,
    top_gap_mm=4.0,
    crown_band_mm=2.0,
    head_zone_mm=32.0,
    chin_band_mm=2.0,
    h_line_width_mm=16.5,
    center_band_mm=3.0,
    horizontal_tolerance_mm=1.5,
)


SPECS = {"finnish": FINNISH}


def default_pixel_size(spec: PassportSpec, dpi: int = 350) -> tuple[int, int]:
    mm_per_inch = 25.4
    w = round(spec.photo_w_mm / mm_per_inch * dpi)
    h = round(spec.photo_h_mm / mm_per_inch * dpi)
    return w, h
