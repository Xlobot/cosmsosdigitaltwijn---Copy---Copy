import math
import numpy as np

# Physical constants
MU_EARTH = 398600.4418  # km^3 / s^2
R_EARTH = 6378.137      # km (WGS84 equatorial radius)
FLATTENING = 1.0 / 298.257223563
J2 = 1.08262668e-3      # Earth oblateness coefficient
OMEGA_EARTH = 7.2921159e-5  # rad/s (Earth rotation rate)

# Sun direction fitted to cosmos_twin_dataset.xlsx (2019-12-09 ISS-like arc)
# Cylindrical-shadow match ≈ 95%+ across the full dataset.
DEFAULT_SUN_ECI = np.array([-0.86517776, 0.0383072, 0.5])
DEFAULT_SUN_ECI = DEFAULT_SUN_ECI / np.linalg.norm(DEFAULT_SUN_ECI)


def solve_kepler(M: float, e: float, tolerance: float = 1e-8, max_iter: int = 50) -> float:
    """Solve Kepler's equation M = E - e*sin(E) for Eccentric Anomaly E."""
    M = M % (2.0 * math.pi)
    E = M if e < 0.8 else math.pi
    for _ in range(max_iter):
        f = E - e * math.sin(E) - M
        f_prime = 1.0 - e * math.cos(E)
        delta = f / f_prime
        E -= delta
        if abs(delta) < tolerance:
            break
    return E


def true_to_eccentric(nu_rad: float, e: float) -> float:
    """Convert true anomaly to eccentric anomaly (stable atan2 form)."""
    cos_nu = math.cos(nu_rad)
    sin_nu = math.sin(nu_rad)
    denom = 1.0 + e * cos_nu
    if abs(denom) < 1e-12:
        denom = 1e-12 if denom >= 0 else -1e-12
    cos_E = (e + cos_nu) / denom
    sin_E = (math.sqrt(max(0.0, 1.0 - e * e)) * sin_nu) / denom
    return math.atan2(sin_E, cos_E)


def eccentric_to_true(E: float, e: float) -> float:
    """Convert eccentric anomaly to true anomaly (stable atan2 form)."""
    cos_E = math.cos(E)
    sin_E = math.sin(E)
    denom = 1.0 - e * cos_E
    if abs(denom) < 1e-12:
        denom = 1e-12 if denom >= 0 else -1e-12
    cos_nu = (cos_E - e) / denom
    sin_nu = (math.sqrt(max(0.0, 1.0 - e * e)) * sin_E) / denom
    return math.atan2(sin_nu, cos_nu)


def keplerian_to_cartesian(a: float, e: float, inc_deg: float, raan_deg: float,
                           argp_deg: float, nu_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Convert orbital elements (km, deg) to ECI position (km) and velocity (km/s)."""
    inc = math.radians(inc_deg)
    raan = math.radians(raan_deg)
    argp = math.radians(argp_deg)
    nu = math.radians(nu_deg)

    p = a * (1.0 - e**2)
    if p <= 0:
        p = a

    r_mag = p / (1.0 + e * math.cos(nu))

    r_pqw = np.array([
        r_mag * math.cos(nu),
        r_mag * math.sin(nu),
        0.0
    ])

    sqrt_mu_p = math.sqrt(MU_EARTH / max(p, 1e-5))
    v_pqw = np.array([
        -sqrt_mu_p * math.sin(nu),
        sqrt_mu_p * (e + math.cos(nu)),
        0.0
    ])

    cos_O, sin_O = math.cos(raan), math.sin(raan)
    cos_w, sin_w = math.cos(argp), math.sin(argp)
    cos_i, sin_i = math.cos(inc), math.sin(inc)

    R = np.array([
        [cos_O * cos_w - sin_O * sin_w * cos_i, -cos_O * sin_w - sin_O * cos_w * cos_i, sin_O * sin_i],
        [sin_O * cos_w + cos_O * sin_w * cos_i, -sin_O * sin_w + cos_O * cos_w * cos_i, -cos_O * sin_i],
        [sin_w * sin_i, cos_w * sin_i, cos_i]
    ])

    r_eci = R @ r_pqw
    v_eci = R @ v_pqw
    return r_eci, v_eci


def cartesian_to_keplerian(r_eci: np.ndarray, v_eci: np.ndarray) -> dict:
    """Convert ECI state vectors to classical orbital elements (km, deg)."""
    r_mag = float(np.linalg.norm(r_eci))
    v_mag = float(np.linalg.norm(v_eci))
    h_vec = np.cross(r_eci, v_eci)
    h_mag = float(np.linalg.norm(h_vec))
    if h_mag < 1e-12 or r_mag < 1e-12:
        return {
            "semi_major_axis": r_mag,
            "eccentricity": 0.0,
            "inclination": 0.0,
            "raan": 0.0,
            "argument_of_perigee": 0.0,
            "true_anomaly": 0.0,
        }

    n_vec = np.array([-h_vec[1], h_vec[0], 0.0])
    n_mag = float(np.linalg.norm(n_vec))

    e_vec = (1.0 / MU_EARTH) * np.cross(v_eci, h_vec) - (r_eci / r_mag)
    e = float(np.linalg.norm(e_vec))

    energy = (v_mag**2 / 2.0) - (MU_EARTH / r_mag)
    if abs(energy) > 1e-12:
        a = -MU_EARTH / (2.0 * energy)
    else:
        a = r_mag

    inc = math.degrees(math.acos(np.clip(h_vec[2] / h_mag, -1.0, 1.0)))

    if n_mag > 1e-12:
        raan = math.degrees(math.atan2(n_vec[1], n_vec[0])) % 360.0
        if e > 1e-8:
            argp = math.degrees(math.atan2(
                float(np.dot(np.cross(n_vec, e_vec), h_vec) / h_mag),
                float(np.dot(n_vec, e_vec))
            )) % 360.0
        else:
            argp = 0.0
    else:
        raan = 0.0
        argp = 0.0

    if e > 1e-8:
        nu = math.degrees(math.atan2(
            float(np.dot(np.cross(e_vec, r_eci), h_vec) / h_mag),
            float(np.dot(e_vec, r_eci))
        )) % 360.0
    else:
        # Circular: true anomaly from nodal vector / position
        if n_mag > 1e-12:
            nu = math.degrees(math.atan2(
                float(np.dot(np.cross(n_vec, r_eci), h_vec) / h_mag),
                float(np.dot(n_vec, r_eci))
            )) % 360.0
        else:
            nu = math.degrees(math.atan2(r_eci[1], r_eci[0])) % 360.0

    return {
        "semi_major_axis": float(a),
        "eccentricity": float(max(0.0, e)),
        "inclination": float(inc),
        "raan": float(raan),
        "argument_of_perigee": float(argp),
        "true_anomaly": float(nu),
    }


def cartesian_to_geodetic(r_eci: np.ndarray, gmst_rad: float = 0.0) -> tuple[float, float, float]:
    """
    Convert ECI position vector (km) to Geodetic Latitude (°), Longitude (°), and Altitude (km).
    """
    x_eci, y_eci, z = r_eci[0], r_eci[1], r_eci[2]
    cos_g, sin_g = math.cos(gmst_rad), math.sin(gmst_rad)
    x = cos_g * x_eci + sin_g * y_eci
    y = -sin_g * x_eci + cos_g * y_eci

    lon_deg = math.degrees(math.atan2(y, x))
    p = math.sqrt(x**2 + y**2)

    lat = math.atan2(z, p * (1.0 - (2.0 * FLATTENING - FLATTENING**2)))
    for _ in range(5):
        sin_lat = math.sin(lat)
        N = R_EARTH / math.sqrt(1.0 - (2.0 * FLATTENING - FLATTENING**2) * sin_lat**2)
        lat = math.atan2(z + (2.0 * FLATTENING - FLATTENING**2) * N * sin_lat, p)

    sin_lat = math.sin(lat)
    N = R_EARTH / math.sqrt(1.0 - (2.0 * FLATTENING - FLATTENING**2) * sin_lat**2)
    alt_km = p / math.cos(lat) - N if abs(math.cos(lat)) > 1e-6 else abs(z) - R_EARTH
    lat_deg = math.degrees(lat)

    return float(lat_deg), float(lon_deg), float(alt_km)


def is_sunlit(r_eci: np.ndarray, sun_vec_eci: np.ndarray = None) -> bool:
    """
    Check if satellite is in sunlight or Earth's cylindrical shadow.
    """
    if sun_vec_eci is None:
        sun_vec_eci = DEFAULT_SUN_ECI

    sun_norm = np.asarray(sun_vec_eci, dtype=float)
    n = np.linalg.norm(sun_norm)
    if n < 1e-12:
        sun_norm = DEFAULT_SUN_ECI
    else:
        sun_norm = sun_norm / n

    r_dot_s = float(np.dot(r_eci, sun_norm))
    if r_dot_s > 0:
        return True

    r_perp = float(np.linalg.norm(r_eci - r_dot_s * sun_norm))
    return bool(r_perp > R_EARTH)


def estimate_sun_vector(positions: np.ndarray, sunlit_flags: np.ndarray) -> np.ndarray:
    """
    Fit a unit sun vector in ECI that best reproduces observed sunlit flags.
    Falls back to DEFAULT_SUN_ECI when history is too short.
    """
    positions = np.asarray(positions, dtype=float)
    flags = np.asarray(sunlit_flags, dtype=bool)
    if len(positions) < 5:
        return DEFAULT_SUN_ECI.copy()

    best_score = -1.0
    best_vec = DEFAULT_SUN_ECI.copy()

    # Coarse grid — fast enough for a 30-row history window
    for lon_deg in np.linspace(0.0, 360.0, 36, endpoint=False):
        for lat_deg in np.linspace(-35.0, 35.0, 15):
            lon = math.radians(float(lon_deg))
            lat = math.radians(float(lat_deg))
            sun = np.array([
                math.cos(lat) * math.cos(lon),
                math.cos(lat) * math.sin(lon),
                math.sin(lat),
            ])
            dots = positions @ sun
            # Cylindrical shadow: lit if in front of Earth OR outside cylinder
            r_perp = np.linalg.norm(positions - dots[:, None] * sun[None, :], axis=1)
            pred = (dots > 0) | (r_perp > R_EARTH)
            score = float(np.mean(pred == flags))
            if score > best_score:
                best_score = score
                best_vec = sun

    if best_score < 0.6:
        return DEFAULT_SUN_ECI.copy()
    return best_vec / np.linalg.norm(best_vec)


def propagate_orbit_step(
    a: float, e: float, inc: float, raan: float, argp: float, nu: float,
    dt_seconds: float, delta_v_vector: np.ndarray = None,
    sun_vec_eci: np.ndarray = None
) -> dict:
    """
    Propagates Keplerian elements forward by dt_seconds, including J2 nodal precession
    and optional impulsive Delta-V.
    """
    e = max(0.0, min(float(e), 0.99))
    a = max(float(a), R_EARTH + 150.0)
    n = math.sqrt(MU_EARTH / (a**3))  # Mean motion (rad/s)

    nu_rad = math.radians(nu)
    E0 = true_to_eccentric(nu_rad, e)
    M0 = E0 - e * math.sin(E0)

    p = a * (1.0 - e**2)
    p = max(p, 1.0)
    raan_rate = -1.5 * J2 * (R_EARTH / p)**2 * n * math.cos(math.radians(inc))
    argp_rate = 0.75 * J2 * (R_EARTH / p)**2 * n * (5.0 * math.cos(math.radians(inc))**2 - 1.0)

    M_new = M0 + n * dt_seconds
    raan_new = (raan + math.degrees(raan_rate * dt_seconds)) % 360.0
    argp_new = (argp + math.degrees(argp_rate * dt_seconds)) % 360.0

    E_new = solve_kepler(M_new, e)
    nu_new_deg = math.degrees(eccentric_to_true(E_new, e)) % 360.0

    r_eci, v_eci = keplerian_to_cartesian(a, e, inc, raan_new, argp_new, nu_new_deg)

    if delta_v_vector is not None and np.linalg.norm(delta_v_vector) > 0:
        v_eci = v_eci + np.asarray(delta_v_vector, dtype=float)
        oe = cartesian_to_keplerian(r_eci, v_eci)
        a = oe["semi_major_axis"]
        e = oe["eccentricity"]
        inc = oe["inclination"]
        raan_new = oe["raan"]
        argp_new = oe["argument_of_perigee"]
        nu_new_deg = oe["true_anomaly"]
        r_eci, v_eci = keplerian_to_cartesian(a, e, inc, raan_new, argp_new, nu_new_deg)

    sunlit = is_sunlit(r_eci, sun_vec_eci)

    return {
        "semi_major_axis": float(a),
        "eccentricity": float(e),
        "inclination": float(inc),
        "raan": float(raan_new % 360.0),
        "argument_of_perigee": float(argp_new % 360.0),
        "true_anomaly": float(nu_new_deg),
        "position_x": float(r_eci[0]),
        "position_y": float(r_eci[1]),
        "position_z": float(r_eci[2]),
        "velocity_x": float(v_eci[0]),
        "velocity_y": float(v_eci[1]),
        "velocity_z": float(v_eci[2]),
        "sunlit": bool(sunlit)
    }
