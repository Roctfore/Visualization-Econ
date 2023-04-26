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

state_GDP = pd.read_csv("SAGDP1__ALL_AREAS_1997_2022.csv", skipfooter=4, engine='python')
state_GDP['GeoFIPS'] = state_GDP['GeoFIPS'].map(lambda x: x.lstrip(' "').rstrip('0"'))
state_GDP['GeoFIPS'] = state_GDP['GeoFIPS'].apply(lambda x: x + '0' if len(x) == 1 else x)
state_GDP = state_GDP[state_GDP['LineCode'] == 1]
state_GDP = state_GDP.drop(['Region', 'TableName', 'TableName', 'LineCode','IndustryClassification', 'Description', 'Unit'], axis=1)
# Create a new dataframe with 'GeoFIPS', 'GeoName', 'year', and 'GDP' columns
state_GDP_melted = pd.melt(state_GDP, id_vars=['GeoFIPS', 'GeoName'], var_name='year', value_name='GDP')

# Convert 'year' column from string to int
state_GDP_melted['year'] = state_GDP_melted['year'].astype(int)

# Sort the dataframe by 'GeoFIPS' and 'year'
state_GDP_melted = state_GDP_melted.sort_values(['GeoFIPS', 'year'])

# Reset the index
state_GDP_melted = state_GDP_melted.reset_index(drop=True)
# Create a new dataframe with the relevant columns
state_GDP_melted['GDP'] = pd.to_numeric(state_GDP_melted['GDP'], errors='coerce')
state_gdp_growth = state_GDP_melted[['GeoFIPS','GeoName', 'year', 'GDP']].copy()

# Calculate the GDP growth rate for each state
state_gdp_growth['GDP_growth_rate'] = state_gdp_growth.groupby('GeoFIPS')['GDP'].pct_change()

# Remove the first year (1997) for each state
state_gdp_growth = state_gdp_growth[state_gdp_growth['year'] > 1997]

# Reset the index
state_gdp_growth.reset_index(drop=True, inplace=True)
state_gdp_growth_only = state_gdp_growth.loc[state_gdp_growth['GeoName'] != 'United States']
state_gdp_growth_only = state_gdp_growth_only[ (state_gdp_growth_only['GeoFIPS'].astype(int) <= 56)]
# Convert FIPS to string
state_gdp_growth_only['year'] = state_gdp_growth_only['year'].astype(int)



app = dash.Dash(__name__)

app.layout = html.Div([
    html.Div([
        dcc.Graph(id='map-unemployment', figure=go.Figure()),
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
        dcc.Graph(id='map-gdp', figure=go.Figure())
    ]),
    html.Div([
        dcc.Graph(id='map-gdp-growth', figure=go.Figure())
    ]),
    html.Div([
        dcc.Graph(id='line-chart-unemployment', figure=go.Figure())
    ]),
    html.Div([
        dcc.Graph(id='line-chart-gdp-growth', figure=go.Figure())
    ])
])

@app.callback(
    Output('map-unemployment', 'figure'),
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
    Output('line-chart-unemployment', 'figure'),
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

# Add callback functions for the new maps and line chart
@app.callback(
    Output('map-gdp', 'figure'),
    [Input('year-slider', 'value')])
def update_gdp_choropleth_map(year):
    # Create the traces for GDP and GDP growth rate
    fig_gdp = px.choropleth_mapbox(
        state_gdp_growth_only,
        geojson=us_states_geojson,
        locations='GeoFIPS',
        color='GDP',
        color_continuous_scale='Reds',
        animation_frame='year',
        hover_name='GeoName',
        hover_data=['GDP'],
        range_color=(state_gdp_growth_only['GDP'].min(), state_gdp_growth_only['GDP'].max()),
        mapbox_style="carto-positron",
        zoom=3, center={"lat": 37.0902, "lon": -95.7129},
        opacity=0.5,
    )

    # Update the layout
    fig_gdp.update_layout(
        title=dict(x=0.5, xanchor="center"),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="US States GDP (1998-2022)"),
    )
    return fig_gdp

@app.callback(
    Output('map-gdp-growth', 'figure'),
    [Input('year-slider', 'value')])
def update_gdp_growth_choropleth_map(year):
    fig_gdp_growth = px.choropleth_mapbox(
        state_gdp_growth_only,
        geojson=us_states_geojson,
        locations='GeoFIPS',
        color='GDP_growth_rate',
        color_continuous_scale='Greens',
        animation_frame='year',
        hover_name='GeoName',
        hover_data=['GDP_growth_rate'],
        range_color=(state_gdp_growth_only['GDP_growth_rate'].min(), state_gdp_growth_only['GDP_growth_rate'].max()),
        mapbox_style="carto-positron",
        zoom=3, center={"lat": 37.0902, "lon": -95.7129},
        opacity=0.5,
    )

    # Update the layout
    fig_gdp_growth.update_layout(
        title=dict(x=0.5, xanchor="center"),
        margin={"r": 0, "t": 40, "l": 0, "b": 0},
        coloraxis_colorbar=dict(title="US States GDP Growth Rate (1998-2022)"),
    )

    return fig_gdp_growth

@app.callback(
    Output('line-chart-gdp-growth', 'figure'),
    [Input('year-slider', 'value')])
def update_gdp_growth_line_chart(year):
    # Calculate the US average GDP growth rate for each year
    us_average_gdp_growth = state_gdp_growth_only.groupby('year')['GDP_growth_rate'].mean().reset_index()
    us_average_gdp_growth['GeoName'] = 'US Average'

    # Append the US average GDP growth rate to the state GDP growth rate DataFrame
    all_gdp_growth = pd.concat([state_gdp_growth_only, us_average_gdp_growth], ignore_index=True)

    # Create the line chart
    fig_gdp_growth_line = go.Figure()

    # Add a trace for each state and the US average
    for state in all_gdp_growth['GeoName'].unique():
        state_data = all_gdp_growth[all_gdp_growth['GeoName'] == state]
        fig_gdp_growth_line.add_trace(
            go.Scatter(
                x=state_data['year'],
                y=state_data['GDP_growth_rate'],
                name=state,
                visible=False
            )
        )

    # Make the US average trace visible by default
    fig_gdp_growth_line.data[-1].visible = True

    # Create buttons for the first dropdown menu (Selection)
    buttons1 = [dict(
        label=state,
        method='update',
        args=[{'visible': [s == state for s in all_gdp_growth['GeoName'].unique()]},
            {'title': f'GDP Growth Rate: {state}'}])
        for state in all_gdp_growth['GeoName'].unique()]

    # Create buttons for the second dropdown menu (Comparison)
    def create_button2(state):
        idx = all_gdp_growth['GeoName'].unique().tolist().index(state)
        new_visible = [fig_gdp_growth_line.data[i].visible for i in range(len(fig_gdp_growth_line.data))]
        new_visible[idx] = not new_visible[idx]
        return dict(label=state, method='update', args=[{'visible': new_visible}, {}])

    buttons2 = [create_button2(state) for state in all_gdp_growth['GeoName'].unique()]

    # Add the dropdown menus to the layout
    fig_gdp_growth_line.update_layout(
        updatemenus=[
            dict(
                type='dropdown',
                showactive=True,
                buttons=buttons1,
                direction="down",
                pad={"r": 10, "t": 10},
                x=1.2,
                xanchor="left",
                y=1.1,
                yanchor="top",
                bgcolor="lightgrey",
            ),
            dict(
                type='dropdown',
                showactive=True,
                buttons=buttons2,
                direction="down",
                pad={"r": 10, "t": 10},
                x=1.2,
                xanchor="left",
                y=0.8,
                yanchor="top",
                bgcolor="lightgrey",
            )
        ],
        annotations=[
            dict(
                x=1.3,
                y=1.13,
                xref="paper",
                yref="paper",
                text="Selection:",
                showarrow=False,
                font=dict(size=14)
            ),
            dict(
                x=1.3,
                y=0.85,
                xref="paper",
                yref="paper",
                text="Comparison:",
                showarrow=False,
                font=dict(size=14)
            )
        ]
    )
    # Update the layout
    fig_gdp_growth_line.update_layout(
        title=dict(text="GDP Growth Rate: US Average", x=0.5, xanchor="center"),
        xaxis_title="Year",
        yaxis_title="GDP Growth Rate",
    )
    return fig_gdp_growth_line

if __name__ == '__main__':
    app.run_server(debug=True)