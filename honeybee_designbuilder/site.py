# coding=utf-8
"""A module for functions related to DesignBuilder site and climate."""
import os
import math

EARTH_RADIUS = 6371.0  # Earth's radius in kilometers


def haversine(lat1, lon1, lat2, lon2):
    """Calculate the great-circle distance in kilometers between two points."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = (math.sin(dphi / 2) ** 2 +
         math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return EARTH_RADIUS * c


def find_closest_location(target_lat, target_lon, library_path=None):
    """Get the data of the closest location in the DesignBuilder climate library.

    Args:
        target_lat: The latitude of the project site location, for which the
            data of the closest climate file in the climate library will be returned.
        target_lon: The longitude of the project site location, for which the
            data of the closest climate file in the climate library will be returned.
        library_path: Optional path the the DesignBuilder climate library file.
            If None, the LocationTemplates.dat file within this package will
            be used. (Default: None).

    Returns:
        A dictionary with keys representing different DesignBuilder location
        properties and values representing the closest location to the
        target_lat and target_lon in the DesignBuilder climate library.
        Will be None if no closest location could be determined.
    """
    # specify the location of the DesignBuilder climate library file
    if library_path is None:
        package_dir = os.path.dirname(os.path.abspath(__file__))
        library_path = os.path.join(package_dir, 'LocationTemplates.dat')

    # get the row of the closest station in the DesignBuilder climate library
    field_names = []
    closest_station = []
    min_distance = float('inf')
    with open(library_path, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            line = line.strip()
            # Skip empty lines or the two header lines
            if not line or i in (0, 1):
                if i == 1:
                    field_names = [p.strip() for p in line.split('#')]
                continue

            # Split by '#' and strip trailing whitespace from each field
            parts = [p.strip() for p in line.split('#')]

            # Ensure the row has enough columns to contain Latitude and Longitude
            if len(parts) < 8:
                continue

            # get the latitude and longitude
            try:
                lat = float(parts[6])
                lon = float(parts[7])
            except ValueError:
                continue  # Skip any malformed lines

            # evaluate if the location is closer than the currently selected one
            dist = haversine(target_lat, target_lon, lat, lon)
            if dist < min_distance:
                min_distance = dist
                closest_station = parts

    # return all properties of the closest station that was found
    if len(field_names) == len(closest_station):
        station_data = {}
        for key, value in zip(field_names, closest_station):
            station_data[key] = value
        return station_data


def modify_template_for_site(xml_template, project_info):
    """Modify an ElementTree of a DesignBuilder template given a ProjectInfo object.

    This involves setting the BuildingOrientation in the template using the
    north defined in the project_info. If the project_info contains a location,
    this will also be used to set all of the location attributes and also
    set the weather data to the closest location found in the DesignBuilder
    climate library. This means that the weather_urls contained in the
    project_info are always ignored given that DesignBuilder does not accept
    external weather files and sets everything up using its own internal
    climate library.

    Args:
        xml_template: The root of an ElementTree parsed from a DesignBuilder template.
        project_info: A Ladybug ProjectInfo object to set the site attributes of
            the project.
    """
    # get the list of attributes to be set using the project_info
    xml_site = xml_template.find('Site')
    xml_attrs = xml_site.find('Attributes')

    # set the BuildingOrientation using the north
    xml_orient = xml_attrs.find('.//Attribute[@name="BuildingOrientation"]')
    xml_orient.text = str(round(project_info.north, 1))

    # if there is a location, use it to set all of the weather data
    if project_info.location:
        loc = project_info.location

        # set basic properties from the DesignBuilder climate library
        loc_data = find_closest_location(loc.latitude, loc.longitude)
        if loc_data:
            for key, value in loc_data.items():
                if key == 'Id':
                    key = 'LocationTemplateId'
                xml_attr = xml_attrs.find('.//Attribute[@name="{}"]'.format(key))
                if xml_attr is not None:
                    xml_orient.text = value

        # overwrite the latitude and longitude with that specific to the project
        xml_lat = xml_attrs.find('.//Attribute[@name="Latitude"]')
        xml_lat.text = str(round(loc.latitude, 2))
        xml_lon = xml_attrs.find('.//Attribute[@name="Longitude"]')
        xml_lon.text = str(round(loc.longitude, 2))
        xml_elev = xml_attrs.find('.//Attribute[@name="Elevation"]')
        xml_elev.text = str(round(loc.elevation, 2))

    return xml_template
