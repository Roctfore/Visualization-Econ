import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from urllib.request import urlopen
import json
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
# Load state_year.csv data
state_year = pd.read_csv("state_year_unemployment.csv")

# Convert data to long format
source = state_year.rename(columns={"fips": "FIPS", "unem_rate": "UnemploymentRate"})[["FIPS", "state", "year", "UnemploymentRate"]]

source = source[["FIPS", "state", "year", "UnemploymentRate"]]
#usvi_data = pd.DataFrame({"FIPS": [78], "state": ["U.S. Virgin Islands"], "year": [np.nan], "UnemploymentRate": [np.nan]})
#source = pd.concat([source, usvi_data], ignore_index=True)

# Convert the FIPS codes to two-digit strings
source['FIPS'] = source['FIPS'].apply(lambda x: f"{x:02d}")

# Convert the 'year' field in merged_data to a string
source['year'] = source['year'].astype(int)
source['FIPS'] = source['FIPS'].astype(str)

with urlopen('https://raw.githubusercontent.com/PublicaMundi/MappingAPI/master/data/geojson/us-states.json') as response:
    us_states_geojson = json.load(response)

app = dash.Dash(__name__)

app.layout = html.Div([
    html.Div([
        dcc.Graph(id='map', figure=go.Figure()),
        dcc.Slider(
            id='year-slider',
            min=source['year'].min(), 
            max=source['year'].max(), 
            value=source['year'].min(), 
            marks={str(year): str(year) for year in source['year'].unique()}, 
            step=None
        )
    ]),
    html.Div([
        dcc.Graph(id='line-chart', figure=go.Figure())
    ])
])


@app.callback(
    Output('map', 'figure'),
    [Input('year-slider', 'value')])
def update_choropleth_map(year):
    source_year = source[source['year'] == year]

    fig_states = px.choropleth_mapbox(
        source_year,
        geojson=us_states_geojson,
        locations='FIPS',
        color='UnemploymentRate',
        color_continuous_scale='Viridis',
        animation_frame='year',
        hover_name='state',
        hover_data=['UnemploymentRate'],
        labels={'UnemploymentRate': 'Unemployment Rate'},
        title=f'US Unemployment Rates by State ({year})',
        range_color=(0, 12),
        mapbox_style="carto-positron",
        zoom=3, center={"lat": 37.0902, "lon": -95.7129},
        opacity=0.5,
    )

    fig_states.update_layout(
        title=dict(x=0.5, xanchor="center"),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="Unemployment Rate"),
    )

    return fig_states

@app.callback(
    Output('line-chart', 'figure'),
    [Input('year-slider', 'value')])
def update_line_chart(year):
    # Get the rows with max and min UnemploymentRate for each year
    max_rows = source.loc[source.groupby('year')['UnemploymentRate'].idxmax()]
    min_rows = source.loc[source.groupby('year')['UnemploymentRate'].idxmin()]

    # Merge max and min rows into a single DataFrame
    yearly_stats = max_rows.merge(min_rows, on='year', suffixes=('_max', '_min'))

    # Calculate average UnemploymentRate for each year
    yearly_avg = source.groupby('year').agg({'UnemploymentRate': 'mean'}).reset_index()
    yearly_avg.columns = ['year', 'avg_rate']

    # Merge average UnemploymentRate into the yearly_stats DataFrame
    yearly_stats = yearly_stats.merge(yearly_avg, on='year')

    # Create figure
    fig = go.Figure()

    # Add traces for highest, lowest, and average UnemploymentRate
    fig.add_trace(go.Scatter(x=yearly_stats['year'], y=yearly_stats['UnemploymentRate_max'], 
                            name='Max Unemployment Rate', mode='lines+markers',
                            text=yearly_stats['state_max'],
                            hovertemplate='Year: %{x}<br>%{text}: %{y}'))

    fig.add_trace(go.Scatter(x=yearly_stats['year'], y=yearly_stats['UnemploymentRate_min'], 
                            name='Min Unemployment Rate', mode='lines+markers',
                            text=yearly_stats['state_min'],
                            hovertemplate='Year: %{x}<br>%{text}: %{y}'))

    fig.add_trace(go.Scatter(x=yearly_stats['year'], y=yearly_stats['avg_rate'], 
                            name='Avg Unemployment Rate', mode='lines+markers',
                            hovertemplate='Year: %{x}<br>Average: %{y}'))

    # Set title
    fig.update_layout(title_text="Yearly Unemployment Rates with Range Slider and Selectors")

    # Add range slider and selectors
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(count=10, label="10y", step="year", stepmode="backward"),
                    dict(count=20, label="20y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True),
            type="date"
        ),
        hovermode='x'
    )

    # Set x-axis date format to display only the year and add a vertical black line on hover
    fig.update_xaxes(
        tickformat="%Y",
        showspikes=True, 
        spikecolor="black", 
        spikesnap="cursor", 
        spikemode="across",
        spikethickness=1
    )

    return fig

if __name__ == '__main__':
    app.run_server(debug=True)