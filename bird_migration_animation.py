import csv
import datetime
import dateutil.parser
import sys
import traceback
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import numpy as np
from collections import defaultdict

import cartopy.crs as ccrs
import cartopy.feature as cfeature

# Hardcode the input CSV and output file paths
csvFile = r"C:\Users\domin\PycharmProjects\birds\clean_bird_migration.csv"     # Replace with your CSV file
outputFile = r"C:\Users\domin\PycharmProjects\birds\2_clean_bird_migration.mp4"  # Replace with desired output file or
# None for just showing
def parseFile(file):
    try:
        with open(file, newline="") as csvfile:
            reader = csv.DictReader(csvfile, delimiter=",", quotechar='"')
            rows = [
                {
                    "id": int(row["occurrenceID"]),
                    "species": row["species"],
                    "coord": [float(row["longitude"]), float(row["latitude"])],
                    "time": row["date"],
                }
                for row in reader
                if row["longitude"] and row["latitude"]
            ]
            return rows
    except FileNotFoundError:
        print('Error: missing file ' + file)
        sys.exit(1)
    except (csv.Error, KeyError):
        print('Error: CSV parsing failed')
        print(traceback.format_exc())
        sys.exit(1)

def groupByBird(observations):
    sortedObs = sorted(observations, key=lambda row: row["id"])
    id_counter = 0
    groups = []
    currentGroup = None
    prevId = -1
    for obs in sortedObs:
        time = dateutil.parser.isoparse(obs["time"])
        if (
            currentGroup
            and obs["id"] == prevId + 1
            and obs["species"] == currentGroup["species"]
            and time > currentGroup["times"][-1]
            and time.year == currentGroup["times"][0].year
        ):
            currentGroup["coords"].append(obs["coord"])
            currentGroup["times"].append(time)
        else:
            if currentGroup:
                groups.append(currentGroup)
            currentGroup = {
                "id": id_counter,
                "species": obs["species"],
                "times": [time],
                "coords": [obs["coord"]],
            }
            id_counter += 1
        prevId = obs["id"]

    if currentGroup:
        groups.append(currentGroup)
    return groups

def normalize_to_single_year(groups, fictional_year=2020):
    for g in groups:
        new_times = []
        for t in g["times"]:
            new_times.append(datetime.datetime(
                fictional_year, t.month, t.day, t.hour, t.minute, t.second, t.microsecond, t.tzinfo))
        g["times"] = new_times
    return groups

def assign_species_colors(groups):
    species_list = list({g["species"] for g in groups})
    species_list.sort()
    # Use the new recommended method to get colormaps
    cmap = plt.get_cmap('tab10', len(species_list))
    species_color_map = {species: cmap(i) for i, species in enumerate(species_list)}
    return species_color_map

def main(csv_file, output_file=None):
    plt.rcParams['figure.dpi'] = 300  # High resolution figures

    # Parse and group data
    observations = parseFile(csv_file)
    groups = groupByBird(observations)
    groups = normalize_to_single_year(groups)

    # Extract day-of-year info to determine the animation range
    all_dates = []
    for g in groups:
        for t in g["times"]:
            all_dates.append(t.timetuple().tm_yday)

    min_day = min(all_dates)
    max_day = max(all_dates)

    # Assign colors to species (consistent throughout the animation)
    species_colors = assign_species_colors(groups)

    # Flatten all points for easy indexing
    points_data = []
    for g in groups:
        for coord, t in zip(g["coords"], g["times"]):
            doy = t.timetuple().tm_yday
            species = g["species"]
            points_data.append((doy, species, coord[0], coord[1]))

    fade_period = 30  # days over which points fade

    # Create figure and cartopy axes with a black themed background
    fig = plt.figure(figsize=(8,10), dpi=300)
    ax = plt.axes(projection=ccrs.PlateCarree())
    fig.patch.set_facecolor('#1F1F1F')  # figure background
    ax.set_facecolor("#1F1F1F")

    # Determine bounding box from data
    all_lons = [p[2] for p in points_data]
    all_lats = [p[3] for p in points_data]
    margin = 0.2
    lon_min, lon_max = min(all_lons), max(all_lons)
    lat_min, lat_max = min(all_lats), max(all_lats)
    lon_range = lon_max - lon_min
    lat_range = lat_max - lat_min

    # Create static legend using figure, so it doesn't get cleared
    # from matplotlib.patches import Patch
    # legend_patches = [Patch(color=species_colors[sp], label=sp) for sp in sorted(species_colors.keys())]
    # # Place legend outside the axes area
    # fig.legend(handles=legend_patches, loc='upper left', frameon=False, fontsize=8, facecolor='black', edgecolor='black', labelcolor='white')

    start_date = datetime.datetime(2020, 1, 1)

    def init():
        return []

    def update(day):
        # Clear everything in the axes
        ax.clear()

        # Redraw the map features after clearing
        ax.set_facecolor("black")
        ax.set_aspect('auto')
        ax.add_feature(cfeature.BORDERS, edgecolor='#3D3D3D', linewidth=0.5)
        ax.coastlines(color='#292929', linewidth=0.5)
        # Add land with a different color
        ax.add_feature(cfeature.LAND, facecolor='#292929')
        # Add ocean with a different color
        ax.add_feature(cfeature.OCEAN, facecolor='#1F1F1F')

        # Reset extent
        ax.set_extent([lon_min - margin*lon_range, lon_max + margin*lon_range,
                       lat_min - margin*lat_range, lat_max + margin*lat_range],
                      crs=ccrs.PlateCarree())

        # Remove axes
        ax.set_axis_off()

        # Current date string
        current_date = start_date + datetime.timedelta(day - 1)
        date_str = current_date.strftime("%B %d")
        # Set the title
        ax.set_title(date_str, color='white', fontsize=12,
             bbox=dict(facecolor='#1F1F1F', edgecolor='none'))

        current_points = [p for p in points_data if p[0] <= day and p[0] >= (day - fade_period)]

        species_groups = defaultdict(list)
        for d, sp, x, y in current_points:
            age = day - d
            alpha = max(0, 1 - (age / fade_period))
            species_groups[sp].append((x, y, alpha))

        for sp, pts in species_groups.items():
            xs = [pt[0] for pt in pts]
            ys = [pt[1] for pt in pts]
            alphas = [pt[2] for pt in pts]
            base_color = species_colors[sp]
            colors = [(base_color[0], base_color[1], base_color[2], a) for a in alphas]
            ax.scatter(xs, ys, c=colors, s=10, transform=ccrs.PlateCarree())

        return []

    frames = range(min_day, max_day+1)
    anim = animation.FuncAnimation(fig, update, frames=frames, init_func=init, blit=False, repeat=False)

    if output_file:
        anim.save(output_file, writer='ffmpeg', fps=12, dpi=300)
        print(f"Animation saved to {output_file}")
    else:
        plt.show()

if __name__ == "__main__":
    main(csvFile, outputFile)
