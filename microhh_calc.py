import streamlit as st

def cat_list(lst):
    return ' + '.join(lst)

def print_mem(bytes):
    if bytes < 1024:
        return f'{bytes} B'
    elif bytes < 1024**2:
        return f'{bytes / 1024:.2f} KB'
    elif bytes < 1024**3:
        return f'{bytes / (1024**2):.2f} MB'
    elif bytes < 1024**4:
        return f'{bytes / (1024**3):.2f} GB'
    else:
        return f'{bytes / (1024**4):.2f} TB'

def check_grid_decomposition(itot, jtot, ktot, npx, npy):
    errors = []
    if itot%npx != 0:
        errors.append('itot % npx != 0 ')
    if itot%npy != 0:
        errors.append('itot % npy != 0 ')
    if jtot%npx != 0 and npy > 1:
        errors.append('jtot % npx != 0 ')
    if jtot%npy != 0:
        errors.append('jtot % npy != 0 ')
    if ktot%npx != 0:
        errors.append('ktot % npx != 0 ')

    valid = len(errors) == 0

    if valid:
        return True, ''
    else:
        return False, ' + '.join(errors)


st.set_page_config(page_title='MicroHH memory calculator')

st.title('MicroHH 🐏 calculator')

# Keep out of main form such that the form reloads once LES/DNS choice is changed.
col1, col2, col3 = st.columns(3)
with col1:
    precision = st.radio('Float precision (bytes)', options=['Single (4)', 'Double (8)'], index=0, horizontal=True)
with col2:
    hardware = st.radio('Hardware', options=['CPU', 'GPU'], index=0, horizontal=True)
with col3:
    mode = st.radio('Mode', options=['LES', 'DNS'], index=0, horizontal=True)


with st.form('microhh_form'):

    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        itot = st.number_input('itot', min_value=1, value=1024, step=1)
    with col2:
        jtot = st.number_input('jtot', min_value=1, value=1024, step=1)
    with col3:
        ktot = st.number_input('ktot', min_value=1, value=256, step=1)
    with col4:
        npx = st.number_input('npx', min_value=1, value=1, step=1)
    with col5:
        npy = st.number_input('npy', min_value=1, value=1, step=1)

    col1, col2, col3 = st.columns(3)
    with col1:
        if mode == 'DNS':
            sw_advec = st.selectbox('Advection scheme', options=['2', '4', '4m'], index=1)
        else:
            sw_advec = st.selectbox('Advection scheme', options=['2', '2i4', '2i5', '2i62'], index=2)
    with col2:
        if mode == 'DNS':
            sw_diff = st.selectbox('Diffusion scheme', options=['2', '4'], index=1)
        else:
            sw_diff = st.selectbox('Diffusion scheme', options=['Smagorinsky', 'Deardorff TKE'])
    with col3:
        if mode == 'DNS':
            sw_thermo = st.selectbox('Thermodynamics', options=['Disabled', 'Buoyancy'], index=0)
        else:
            sw_thermo = st.selectbox('Thermodynamics', options=['Disabled', 'Buoyancy', 'Dry', 'Moist'], index=3)

    col1, col2, col3 = st.columns(3)
    with col1:
        if mode == 'DNS':
            sw_rad = st.selectbox('Radiation scheme', options=['Disabled'])
        else:
            sw_rad = st.selectbox('Radiation scheme', options=['Disabled', 'RTE+RRTMGP'])
    with col2:
        if mode == 'DNS':
            sw_micro = st.selectbox('Microphysics scheme', options=['Disabled'])
        else:
            sw_micro = st.selectbox('Microphysics scheme', options=['Disabled', 'Single moment ice', 'Double moment warm', 'Double moment ice'])
    with col3:
        n_slist = st.number_input('Number of scalars', min_value=0, max_value=100, value=0, step=1)

    submitted = st.form_submit_button('Calculate', type='primary')

if submitted:

    #
    # Check for invalid combinations.
    #
    if (sw_rad != 'Disabled' or sw_micro != 'Disabled') and sw_thermo != 'Moist':
        st.error('Radiation and/or microphysics schemes require moist thermodynamics.')
        st.stop()

    grid_valid, grid_msg = check_grid_decomposition(itot, jtot, ktot, npx, npy)
    if not grid_valid:
        st.error(f'Invalid grid decomposition: {grid_msg}.')
        st.stop()


    sizeof_TF = 4 if precision == 'Single (4 byte)' else 8

    #
    # Calculations
    #
    if sw_advec == '2':
        ij_gc = 1
        k_gc = 1
    elif sw_advec == '4' or sw_advec == '4m':
        ij_gc = 2
        k_gc = 2
    elif sw_advec == '2i4':
        ij_gc = 2
        k_gc = 1
    elif sw_advec == '2i5' or sw_advec == '2i62':
        ij_gc = 3
        k_gc = 1

    icells = itot + 2 * ij_gc
    jcells = jtot + 2 * ij_gc
    ijcells = icells * jcells
    kcells = ktot + 2 * k_gc
    ncells = ijcells * kcells + 6 * ijcells  # 6 = bot/top fields
    bytes_per_3d = ncells * sizeof_TF

    #
    # Prognostic fields.
    #
    prog_fields = ['u', 'v', 'w']

    if sw_diff == 'Deardorff TKE':
        prog_fields += ['tke']

    if sw_thermo == 'Buoyancy':
        prog_fields += ['b']
    elif sw_thermo == 'Dry':
        prog_fields += ['th']
    elif sw_thermo == 'Moist':
        prog_fields += ['thl', 'qt']

    if sw_micro == 'Single moment ice':
        prog_fields += ['qr', 'qs', 'qg']
    elif sw_micro == 'Double moment warm':
        prog_fields += ['qr', 'nr']
    elif sw_micro == 'Double moment ice':
        prog_fields += ['qi', 'qr', 'qs', 'qg', 'qh', 'ni', 'nr', 'ns', 'ng', 'nh']

    n_prog_fields = len(prog_fields) + n_slist
    if n_slist > 0:
        prog_fields += [f'{n_slist} × scalar']

    #
    # Diagnostic/tmp/help fields.
    #
    n_tmp_fields = 2 if hardware == 'GPU' else 4
    diag_fields = ['p']

    if sw_diff == 'Smagorinsky' or sw_diff == 'Deardorff TKE':
        diag_fields += ['evisc']
    if sw_diff == 'Deardorff TKE' and sw_thermo != 'Disabled':
        diag_fields += ['eviscs']

    n_diag_fields = len(diag_fields)

    if sw_rad == 'RTE+RRTMGP':
        diag_fields += ['3 × RRTMGP fluxes']
        n_diag_fields += 3
        n_tmp_fields += 3

    #
    # Total 3D fields.
    #
    n_3d_fields = 2*n_prog_fields + n_diag_fields + n_tmp_fields

    st.header('Results')

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric('Prognostic 3D fields **', f'{n_prog_fields} × 2')
    with col2:
        st.metric('Diagnostic 3D fields', n_diag_fields)
    with col3:
        st.metric('Temporary 3D fields', n_tmp_fields)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric('Total 3D fields', n_3d_fields)
    with col2:
        st.metric('Memory per 3D field', print_mem(bytes_per_3d))
    with col3:
        st.metric('Total memory', print_mem(n_3d_fields * bytes_per_3d))

    st.header('Notes')
    st.write(f'Prognostic 3D fields: **{cat_list(prog_fields)}**.')
    st.write(f'Diagnostic 3D fields: **{cat_list(diag_fields)}**.')
    st.write(f'Grid points per core/GPU: **{itot * jtot * ktot / npx / npy:.0f}**.')
    st.write(f'_** Low storage Runge Kutta time integration requires two 3D fields per prognostic field._')

else:
    st.info('Configure your MicroHH setup above and hit \"Calculate\".')