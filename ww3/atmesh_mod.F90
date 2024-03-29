!>
!! @mainpage ADCIRC NUOPC Cap
!! @author Saeed Moghimi (moghimis@gmail.com)
!! @date 15/1/17 Original documentation
!------------------------------------------------------
!LOG-----------------
!
!
!

module atmesh_mod

  !-----------------------------------------------------------------------------
  ! ADCIRC mesh utility
  !-----------------------------------------------------------------------------
  use mpi
  use ESMF
  use NUOPC
  USE netcdf

  !use MESH   , only: np,ne,nm,slam,sfea
  !use GLOBAL , only: IMAP_EL_LG,NODES_LG
  !use GLOBAL , only: ETA2, UU2, VV2  ! Export water level and velocity fileds to atmesh model
  !USE GLOBAL,  ONLY: RSNX2, RSNY2    ! Import atmesh 2D forces from atmesh model
  !use SIZES  , only: ROOTDIR


  implicit none
    ! reading data time management info WW3 <-----> ADC exchange
    integer               :: atm_int,atm_num,atm_den
    character (len = 280) :: atm_dir, atm_nam, atm_grd
    character (len = 280) :: FILE_NAME
    character (len =2048) :: info
     
    ! info for reading atmesh netcdf file
    integer               :: nnode,nelem , ntime, noel
    real(ESMF_KIND_R8), allocatable     :: LONS(:), LATS(:),TIMES(:)
    integer           , allocatable     :: TRI(:,:)
    integer           , allocatable     :: TRID(:,:)
    real(ESMF_KIND_R8), allocatable     :: UWND (:,:), VWND(:,:), PRES (:,:)

    ! info for reading structured atmesh netcdf file:
    type strucgrd
!       real(ESMF_KIND_R8), allocatable     :: LONS(:,:), LATS(:,:), TIMES(:)
       real(ESMF_KIND_R8), allocatable     :: UWND(:,:,:), VWND(:,:,:), PRES(:,:,:)
       integer               :: LAT_dimid, LON_dimid       !for structured grid (XYC)
    end type strucgrd
    type(strucgrd) :: atm_strucgrd
    integer               :: nlon, nlat   ! for structured grid (XYC)

    !netcdf vars
    integer :: ncid, NOD_dimid, rec_dimid, ELM_dimid, NOE_dimid
    integer :: LON_varid, LAT_varid, rec_varid, tri_varid
    integer :: UWND_varid, VWND_varid, PRES_varid

     
  
    !> \author Ali Samii - 2016
    !! See: https://github.com/samiiali
    !! \brief This object stores the data required for construction of a parallel or serial
    !! ESMF_Mesh from <tt>fort.14, fort.18, partmesh.txt</tt> files.
    !!
    type meshdata
      !> \details vm is an ESMF_VM object.  ESMF_VM is just an ESMF virtual machine class,
      !! which we will use to get the data about the local PE and PE count.
      type(ESMF_VM)                      :: vm
      !> \details This array contains the node coordinates of the mesh. For
      !! example, in a 2D mesh, the \c jth coordinate of the \c nth node
      !! is stored in location <tt> 2*(n-1)+j</tt> of this array.
      real(ESMF_KIND_R8), allocatable    :: NdCoords(:)
      !> \details This array contains the elevation of different nodes of the mesh
      real(ESMF_KIND_R8), allocatable    :: bathymetry(:)
      !> \details Number of nodes present in the current PE. This is different from the
      !! number of nodes owned by this PE (cf. NumOwnedNd)
      integer(ESMF_KIND_I4)              :: NumNd
      !> \details Number of nodes owned by this PE. This is different from the number of
      !! nodes present in the current PE (cf. NumNd)
      integer(ESMF_KIND_I4)              :: NumOwnedNd
      !> \details Number of elements in the current PE. This includes ghost elements and
      !! owned elements. However, we do not bother to distinguish between owned
      !! element and present element (as we did for the nodes).
      integer(ESMF_KIND_I4)              :: NumEl
      !> \details Number of nodes of each element, which is simply three in 2D ADCIRC.
      integer(ESMF_KIND_I4)              :: NumND_per_El
      !> \details Global node numbers of the nodes which are present in the current PE.
      integer(ESMF_KIND_I4), allocatable :: NdIDs(:)
      !> \details Global element numbers which are present in the current PE.
      integer(ESMF_KIND_I4), allocatable :: ElIDs(:)
      !> \details The element connectivity array, for the present elements in the current PE.
      !! The node numbers are the local numbers of the present nodes. All the element
      !! connectivities are arranged in this one-dimensional array.
      integer(ESMF_KIND_I4), allocatable :: ElConnect(:)
      !> \details The number of the PE's which own each of the nodes present this PE.
      !! This number is zero-based.
      integer(ESMF_KIND_I4), allocatable :: NdOwners(:)
      !> \details An array containing the element types, which are all triangles in our
      !! application.
      integer(ESMF_KIND_I4), allocatable :: ElTypes(:)
      !> \details This is an array, which maps the indices of the owned nodes to the indices of the present
      !! nodes. For example, assume we are on <tt>PE = 1</tt>, and we have four nodes present, and the
      !! first and third nodes belong to <tt>PE = 0</tt>. So we have:
      !! \code
      !! NumNd = 4
      !! NumOwnedNd = 2
      !! NdOwners = (/0, 1, 0, 1/)
      !! NdIDs = (/2, 3, 5, 6/)
      !! owned_to_present = (/2, 4/)    <-- Because the first node owned by this PE is actually
      !!                                    the second node present on this PE, and so on.
      !! \endcode
      integer(ESMF_KIND_I4), allocatable :: owned_to_present_nodes(:)
    end type meshdata

      !! XYC added type griddata for structured grid:
    type griddata
      type(ESMF_VM)                      :: vm
      integer :: maxIndex(2)
      type(ESMF_GridConn_Flag) :: connflagDim1(2)
      type(ESMF_GridConn_Flag) :: connflagDim2(2)
      type(ESMF_CoordSys_Flag) :: coordSys 
    end type griddata


  !-----------------------------------------------------------------------------
  contains

!-----------------------------------------------------------------------
!- Sub !!!????
!-----------------------------------------------------------------------
    SUBROUTINE init_atmesh_nc()
      IMPLICIT NONE
      character (len = *), parameter :: NOD_NAME    = "node"
      character (len = *), parameter :: NOE_NAME    = "noel"
      character (len = *), parameter :: ELM_NAME    = "element"
      character (len = *), parameter :: LAT_NAME    = "latitude"
      character (len = *), parameter :: LON_NAME    = "longitude"
      character (len = *), parameter :: REC_NAME    = "time"
      character (len = *), parameter :: UWND_NAME   = "uwnd"
      character (len = *), parameter :: VWND_NAME   = "vwnd"
      character (len = *), parameter :: PRES_NAME   = "P"
      character (len = *), parameter :: TRI_NAME    = "tri"
      ! for structured grid:
      character (len = *), parameter :: XDIM_NAME    = "lon"
      character (len = *), parameter :: YDIM_NAME    = "lat"
     

      character (len = 140)          :: units
      character(len=*),parameter :: subname='(atmesh_mod:init_atmesh_nc)'


      logical :: THERE
      integer :: lat, lon,i, iret, rc, num
      

      FILE_NAME =  TRIM(atm_dir)//'/'//TRIM(atm_nam)
      print *, ' FILE_NAME  > ', FILE_NAME
      print *, ' atm_grd > ', TRIM(atm_grd)
      INQUIRE( FILE= FILE_NAME, EXIST=THERE )
      if ( .not. THERE)  stop 'ATMESH netcdf grdfile does not exist!'

      ncid = 0
      IF (TRIM(atm_grd) == 'unstructured') THEN
      ! Open the file.
      call check(  nf90_open(trim(FILE_NAME), NF90_NOWRITE, ncid))

      ! Get ID of unlimited dimension
      !call check( nf90_inquire(ncid, unlimitedDimId = rec_dimid) )

      ! Get ID of limited dimension
      call check( nf90_inq_dimid(ncid, REC_NAME, rec_dimid) )
      call check( nf90_inq_dimid(ncid, NOD_NAME, NOD_dimid) )
      call check( nf90_inq_dimid(ncid, ELM_NAME, ELM_dimid) )
      call check( nf90_inq_dimid(ncid, NOE_NAME, NOE_dimid) )

      call check(nf90_inquire_dimension(ncid, NOD_dimid, len = nnode) )
      call check(nf90_inquire_dimension(ncid, ELM_dimid, len = nelem) )
      call check(nf90_inquire_dimension(ncid, NOE_dimid, len = noel) )
      call check(nf90_inquire_dimension(ncid, rec_dimid, len = ntime))

      !print *,  ' nelem  > ',nelem , ' noel  > ' ,noel,  ' ntime > ',ntime

      ! Get the varids of the pressure and temperature netCDF variables.
      call check( nf90_inq_varid(ncid, LAT_NAME,     LAT_varid) )
      call check( nf90_inq_varid(ncid, LON_NAME,     LON_varid) )
      call check( nf90_inq_varid(ncid, REC_NAME,     rec_varid) )
      call check( nf90_inq_varid(ncid, UWND_NAME,    UWND_varid) )
      call check( nf90_inq_varid(ncid, VWND_NAME,    VWND_varid) )
      call check( nf90_inq_varid(ncid, PRES_NAME,    PRES_varid) )
      call check( nf90_inq_varid(ncid, TRI_NAME,     TRI_varid) )

      !allocate vars
      if(.not. allocated(LATS))  allocate (LATS  (1:nnode))
      if(.not. allocated(LONS))  allocate (LONS  (1:nnode))
      if(.not. allocated(TIMES)) allocate (TIMES (1:ntime))
      if(.not. allocated(TRI))   allocate (TRI  (1:noel ,1:nelem))
      if(.not. allocated(TRID))  allocate (TRID (1:noel ,1:nelem))
      ! read vars
      call check(nf90_get_var(ncid, LAT_varid, LATS ))
      call check(nf90_get_var(ncid, LON_varid, LONS ))
      call check(nf90_get_var(ncid, rec_varid, TIMES))
      !call check(nf90_get_var(ncid, UWND_varid, UWND  ))
      !TODO: Why the order is other way???? Might change the whole forcing fields!!!!<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< IMPORTANT <<<<<
      ! plot input and out put to be sure we are not scrambling the data. the same for HWRF netcdf file
      !print *, '-- debugging: get TRI -- '
      ! XYC: TRI 's data type created type conversion problem on RENCI-HATTERAS
      call check(nf90_get_var(ncid, TRI_varid, TRI, start = (/1,1/),count = (/noel,nelem/)  ))
      
      !TRI = int( TRID )
      
      !do num = 1,10
      !    print *,  "TRI", TRI(1,num), TRI(2,num), TRI(3,num)
      !end do
      
      ELSEIF (TRIM(atm_grd) == 'structured') THEN
        ! XYC add code block to read in information from a structured wind input
        ! Open the file.
        call check(  nf90_open(trim(FILE_NAME), NF90_NOWRITE, ncid))

      ! Get ID of unlimited dimension
        call check( nf90_inquire(ncid, unlimitedDimId = rec_dimid) )

      ! Get ID of limited dimension
      !call check( nf90_inq_dimid(ncid, REC_NAME, rec_dimid) )
      call check( nf90_inq_dimid(ncid, XDIM_NAME, atm_strucgrd%LON_dimid) )
      call check( nf90_inq_dimid(ncid, YDIM_NAME, atm_strucgrd%LAT_dimid) )

      ! How many values of "nodes" are there?
      call check(nf90_inquire_dimension(ncid, atm_strucgrd%LON_dimid,  & 
                len = nlon) )
      call check(nf90_inquire_dimension(ncid, atm_strucgrd%LAT_dimid, & 
                len = nlat) )
      ! What is the name of the unlimited dimension, how many records are there?
      call check(nf90_inquire_dimension(ncid, rec_dimid, len = ntime))

      print *,  ' nlon  > ',nlon , ' nlat  > ' ,nlat,  ' ntime > ',ntime

      ! Get the varids of the pressure and temperature netCDF variables.
      call check( nf90_inq_varid(ncid, LAT_NAME,     LAT_varid) )
      call check( nf90_inq_varid(ncid, LON_NAME,     LON_varid) )
      call check( nf90_inq_varid(ncid, REC_NAME,     rec_varid) )
      call check( nf90_inq_varid(ncid, UWND_NAME,    UWND_varid) )
      call check( nf90_inq_varid(ncid, VWND_NAME,    VWND_varid) )
      call check( nf90_inq_varid(ncid, PRES_NAME,    PRES_varid) )

      !allocate vars
      if(.not. allocated(LATS)) then
         allocate (LATS(1:nlat))
      endif
      if(.not. allocated(LONS)) then
          allocate (LONS(1:nlon))
      endif
      if(.not. allocated(TIMES)) allocate (TIMES (1:ntime))
      ! read vars
      call check(nf90_get_var(ncid, LAT_varid, LATS ))
      call check(nf90_get_var(ncid, LON_varid, LONS ))
      call check(nf90_get_var(ncid, rec_varid, TIMES))
      !call check(nf90_get_var(ncid, UWND_varid, UWND  ))
      !TODO: Why the order is other way???? Might change the whole forcing fields!!!!<<<<<<<<<<<<<<<<<<<<<<<<<<<<<<< IMPORTANT <<<<<
      ! plot input and out put to be sure we are not scrambling the data. the same for HWRF netcdf file
      !print *, '-- debugging: get TRI -- '
      ! XYC: TRI 's data type created type conversion problem on RENCI-HATTERAS
      !call check(nf90_get_var(ncid, TRI_varid, TRI, start = (/1,1/),count = (/noel,nelem/)  ))
      
      ENDIF
      write(info,*) subname,' --- init atmesh netcdf file  --- '
      !print *, info
      call ESMF_LogWrite(info, ESMF_LOGMSG_INFO, rc=rc)

    END SUBROUTINE

!-----------------------------------------------------------------------
!- Sub !!!????
!-----------------------------------------------------------------------
    SUBROUTINE read_atmesh_nc(currTime)
      IMPLICIT NONE
      type(ESMF_Time),intent(in)     :: currTime
      type(ESMF_Time)                :: refTime
      type(ESMF_TimeInterval)        :: dTime


      character (len = 140)          :: units
      character(len=*),parameter :: subname='(atmesh_mod:read_atmesh_nc)'
      integer, parameter :: NDIMS = 2
      integer    :: start(NDIMS),count(NDIMS)
      integer    :: start3D(NDIMS+1),count3D(NDIMS+1)
      logical    :: THERE
      real       :: delta_d_all (ntime) , delta_d_ref
      !integer   :: dimids(NDIMS)

      character  :: c1,c2,c3,c4,c5,c6,c7
      integer    :: yy,mm,dd,hh,min,ss
      integer    :: d_d, d_h, d_m, d_s
      integer    :: lat, lon,it, iret, rc

      rc = ESMF_SUCCESS

      !units = "days since 1990-01-01 00:00:00"
      call check(nf90_get_att(ncid,rec_varid,'units',units))
      READ(units,'(a4,a7,i4,a1,i2,a1,i2,a1,i2,a1,i2,a1,i2)',iostat=iret)  &
                   c1,c2,yy,c3,mm,c4,dd,c5,hh,c6,min,c7,ss

      if (iret .ne. 0) then
        print *, 'Fatal error: A non valid time units string was provided'
        stop 'atmesh_mod: read_atmesh_nc'
      end if

      call ESMF_TimeSet(refTime, yy=yy, mm=mm, dd=dd, h=hh, m=min, s=ss, rc=rc)
      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
        line=__LINE__, &
        file=__FILE__)) &
        return  ! bail out
    
      
      dTime = currTime - refTime
      call ESMF_TimeIntervalGet (dTime, d=d_d, h=d_h, m=d_m, s=d_s, rc=rc)
      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
        line=__LINE__, &
        file=__FILE__)) &
        return  ! bail out

      delta_d_ref = d_d + d_h /24.0 + d_m / (24.0 * 60.0) +  d_s / (24.0 * 3600.0)

      do it = 1, ntime
        delta_d_all(it) =  delta_d_ref - TIMES (it)
      end do

      it = minloc(abs(delta_d_all),dim=1)

      if (abs(delta_d_all (it)) .gt. 7200.) then
         write(info,*) subname,' --- STOP ATMesh: Time dif is GT 2 hours ---  '
         call ESMF_LogWrite(info, ESMF_LOGMSG_INFO, rc=rc)
         stop                  ' --- STOP ATMesh: Time dif is GT 2 hours ---  '
      endif

      !it = 1
      !print *, 'atmesh file it index > ',it

      write(info,*) subname,'atmesh file it index > ',it
      !print *, info
      call ESMF_LogWrite(info, ESMF_LOGMSG_INFO, rc=rc)

      
      call ESMF_TimePrint(refTime, preString="ATMESH refTime=  ", rc=rc)
      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
        line=__LINE__, &
        file=__FILE__)) &
        return  ! bail out
      
      !write(info,*) ' Read ATMesh netcdf:',it, 
      !call ESMF_LogWrite(info, ESMF_LOGMSG_INFO, rc=rc)

      IF ( TRIM(atm_grd) == 'unstructured' ) THEN
        !alocate vars
        if(.not. allocated(UWND))   allocate (UWND (1:nnode,1))
        if(.not. allocated(VWND))   allocate (VWND (1:nnode,1))
        if(.not. allocated(PRES))   allocate (PRES (1:nnode,1))

        start = (/ 1   , it/)
        count = (/nnode, 1 /)  !for some reason the order here is otherway around?!

        print *, start+count
        !print *,size(UWND(ntime,:))
        call check( nf90_get_var(ncid,UWND_varid, UWND, start, count) )
        call check( nf90_get_var(ncid,VWND_varid, VWND, start, count) )
        call check( nf90_get_var(ncid,PRES_varid, PRES, start, count) )

      !print *,FILE_NAME , '   HARD CODED for NOWWWW>>>>>     Time index from atmesh file is > ', it, UWND(1:10,1)
      ELSEIF ( TRIM(atm_grd) == 'structured' ) THEN
        !alocate vars
        if(.not. allocated(atm_strucgrd%UWND)) then
            allocate (atm_strucgrd%UWND (1:nlon,1:nlat,1))
        endif
        if(.not. allocated(atm_strucgrd%VWND)) then
            allocate (atm_strucgrd%VWND (1:nlon,1:nlat,1))
        endif
        if(.not. allocated(atm_strucgrd%PRES)) then
            allocate (atm_strucgrd%PRES (1:nlon,1:nlat,1))
        endif

        start3D = (/ 1  , 1   , it/)
        count3D = (/nlon, nlat, 1 /)  !for some reason the order here is otherway around?!

        !print *, start3D+count3D
        print *, "read ATMesh: it=", start3D(3)
        !print *,size(UWND(ntime,:))
        call check( nf90_get_var(ncid,UWND_varid, atm_strucgrd%UWND, start3D, count3D) )
        call check( nf90_get_var(ncid,VWND_varid, atm_strucgrd%VWND, start3D, count3D) )
        call check( nf90_get_var(ncid,PRES_varid, atm_strucgrd%PRES, start3D, count3D) )
        print *, "read ATMesh: max(U)=", maxval(atm_strucgrd%UWND)

      ENDIF    ! end reading info. from unstructured or structured grid
      write(info,*) subname,' --- read ATMesh netcdf file  --- '
      !print *, info
      call ESMF_LogWrite(info, ESMF_LOGMSG_INFO, rc=rc)

    END SUBROUTINE
    !-----------------------------------------------------------------------
    !- Sub !!!????
    !-----------------------------------------------------------------------

    subroutine construct_meshdata_from_netcdf(the_data)
      implicit none
      integer                               :: i1
      integer, parameter                    :: dim1=2, spacedim=2, NumND_per_El=3
      type(meshdata), intent(inout)         :: the_data
      the_data%NumEl = nelem
      the_data%NumNd = nnode
      allocate(the_data%NdIDs(the_data%NumNd))
      allocate(the_data%ElIDs(the_data%NumEl))
      allocate(the_data%NdCoords(dim1*the_data%NumNd))
      allocate(the_data%bathymetry(the_data%NumNd))
      allocate(the_data%ElConnect(NumND_per_El*the_data%NumEl))
      allocate(the_data%NdOwners(the_data%NumNd))
      allocate(the_data%ElTypes(the_data%NumEl))
      allocate(the_data%owned_to_present_nodes(the_data%NumNd))

      do i1 = 1, the_data%NumNd, 1
              the_data%NdIDs(i1)                 = i1
              the_data%NdCoords((i1-1)*dim1 + 1) = LONS(i1)
              the_data%NdCoords((i1-1)*dim1 + 2) = LATS(i1)
      end do
      do i1 = 1, the_data%NumEl, 1
              the_data%ElIDs(i1)                        =   i1
              the_data%ElConnect((i1-1)*NumND_per_El+1) = TRI(1,i1)
              the_data%ElConnect((i1-1)*NumND_per_El+2) = TRI(2,i1)
              the_data%ElConnect((i1-1)*NumND_per_El+3) = TRI(3,i1)
      end do
      !We have only one node therefore:
      the_data%NdOwners = 0                  !process 0 owns all the nodes
      the_data%NumOwnedND = the_data%NumNd   !number of nodes = number of owned nodes
      the_data%owned_to_present_nodes = the_data%NdIDs

      the_data%ElTypes = ESMF_MESHELEMTYPE_TRI

      close(14)
    end subroutine

!-----------------------------------------------------!
!   XYC added: to do 
    subroutine construct_griddata_from_netcdf(the_data)
    implicit none
      type(griddata), intent(inout)         :: the_data

      the_data%maxIndex=(/nlon, nlat/)
      the_data%connflagDim1(1)=ESMF_GRIDCONN_NONE
      the_data%connflagDim1(2)=ESMF_GRIDCONN_NONE
      the_data%connflagDim2(1)=ESMF_GRIDCONN_NONE
      the_data%connflagDim2(2)=ESMF_GRIDCONN_NONE
      the_data%coordSys=ESMF_COORDSYS_SPH_DEG    ! spherical grid in degrees

    end subroutine


    function CreateGrid_ModelGrid(rc)
        type(ESMF_Grid) :: CreateGrid_ModelGrid
        integer, intent(out), optional :: rc
        character(len=*),parameter   :: subname='(hwrf_cap:CreateGrid_ModelGrid)'        

        real(ESMF_KIND_R8), pointer :: coordX(:,:), coordY(:,:)
        integer :: i, j

        print *, '<0>',nlon,nlat
        rc = ESMF_SUCCESS
        CreateGrid_ModelGrid = ESMF_GridCreateNoPeriDim(name="ModelGrid", &
            minIndex=(/1, 1/), &
            maxIndex=(/nlon, nlat/), &
            indexflag=ESMF_INDEX_GLOBAL, &
            !minCornerCoord=(/1.0_ESMF_KIND_R8, 1.0_ESMF_KIND_R8/), &
            !maxCornerCoord=(/100.0_ESMF_KIND_R8, 100.0_ESMF_KIND_R8/), &
            rc=rc)

        print *, '<1> HWRF LONS ', minval(LONS),maxval(LONS)

        print *, '<1> HWRF LATS ', minval(LATS),maxval(LATS)
        ! add coordinates
        call ESMF_GridAddCoord(CreateGrid_ModelGrid, &
            staggerloc=ESMF_STAGGERLOC_CENTER, rc=rc)
        if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
            line=__LINE__, &
            file=__FILE__)) &
            return  ! bail out
        print *, '<2>'

        call ESMF_GridGetCoord(CreateGrid_ModelGrid, coordDim=1, &
            staggerloc=ESMF_STAGGERLOC_CENTER, &
            farrayPtr=coordX, rc=rc)
        if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
            line=__LINE__, &
            file=__FILE__)) &
            return  ! bail out
        print *, '<3>'

        call ESMF_GridGetCoord(CreateGrid_ModelGrid, coordDim=2, &
            staggerloc=ESMF_STAGGERLOC_CENTER, &
            farrayPtr=coordY, rc=rc)
        if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
            line=__LINE__, &
            file=__FILE__)) &
            return  ! bail out
        print *, '<4>'
        ! set coordinates
        do i=1,nlon
            do j=1,nlat
                coordX(i,j) = LONS(i)
                coordY(i,j) = LATS(j)
            enddo
        enddo
    write(info,*) subname,' --- hwrf SetServices completed --- '
    print *,      subname,' --- hwrf SetServices completed --- '
    call ESMF_LogWrite(info, ESMF_LOGMSG_INFO, rc=rc)
       
    end function
    !-----------------------------------------------------------------------
    !- Sub !!!????
    !-----------------------------------------------------------------------
    subroutine check(status)
      integer, intent ( in) :: status

      if(status /= nf90_noerr) then
        print *, trim(nf90_strerror(status))
        stop
      end if
    end subroutine check

    !-----------------------------------------------------------------------
    !- Sub !!!????
    !-----------------------------------------------------------------------
    FUNCTION Replace_Text (s,text,rep)  RESULT(outs)
      CHARACTER(*)        :: s,text,rep
      CHARACTER(LEN(s)+300) :: outs     ! provide outs with extra char len
      INTEGER             :: i, nt, nr

      outs = s ; nt = LEN_TRIM(text) ; nr = LEN_TRIM(rep)
        DO
           i = INDEX(outs,text(:nt)) ; IF (i == 0) EXIT
           outs = outs(:i-1) // rep(:nr) // outs(i+nt:)
        END DO
    END FUNCTION Replace_Text

    !-----------------------------------------------------------------------
    !- Sub !!!????
    !-----------------------------------------------------------------------
    subroutine update_atmesh_filename (YY, MM, DD, H)
      integer             :: YY, MM, DD, H
      CHARACTER(len=280)      :: inps     ! provide outs with extra 100 char len
      CHARACTER(len=4)        :: year
      CHARACTER(len=2)        :: mon,day
      CHARACTER(len=3)        :: hours

      ! example:  atm_nam: atmesh.Constant.YYYYMMDD_sxy.nc
      inps = trim(atm_nam)

      write(year,"(I4.4)") YY
      inps =  Replace_Text (inps,'YYYY',year)

      write(mon,"(I2.2)")  MM
      inps =  Replace_Text (inps,'MM',mon)

      write(day,"(I2.2)")  DD
      inps =  Replace_Text (inps,'DD',day)

      !past hours from start date
      !write(hours,"(I3.3)") H
      !inps =  Replace_Text (inps,'HHH',hours)

      FILE_NAME =  TRIM(atm_dir)//'/'//TRIM(inps)

    END subroutine update_atmesh_filename


    !-----------------------------------------------------------------------
    !- Sub !!!????
    !-----------------------------------------------------------------------
    !> \author Ali Samii - 2016
    !! See: https://github.com/samiiali
    !> @details Using the data available in <tt> fort.14, fort.18, partmesh.txt</tt> files
    !! this function extracts the scalars and arrays required for construction of a
    !! meshdata object.
    !! After calling this fucntion, one can call create_parallel_esmf_mesh_from_meshdata()
    !! or create_masked_esmf_mesh_from_data() to create an ESMF_Mesh.
    !! @param vm This is an ESMF_VM object, which will be used to obtain the \c localPE
    !! and \c peCount of the \c MPI_Communicator.
    !! @param global_fort14_dir This is the directory path (relative to the executable
    !! or an absolute path) which contains the global \c fort.14 file (not the fort.14
    !! after decomposition).
    !! @param the_data This is the output meshdata object.
    !!

    !> \details As the name of this function suggests, this funciton creates a parallel
    !! ESMF_Mesh from meshdata object. This function should be called collectively by
    !! all PEs for the parallel mesh to be created. The function, extract_parallel_data_from_mesh()
    !! should be called prior to calling this function.
    !! \param the_data This the input meshdata object.
    !! \param out_esmf_mesh This is the ouput ESMF_Mesh object.
    subroutine create_parallel_esmf_mesh_from_meshdata(the_data, out_esmf_mesh)
      implicit none
      type(ESMF_Mesh), intent(out)                  :: out_esmf_mesh
      type(meshdata), intent(in)                    :: the_data
      integer, parameter                            :: dim1=2, spacedim=2, NumND_per_El=3
      integer                                       :: rc
      ! This function is 33.4.7 create a mesh all at once.
      out_esmf_mesh=ESMF_MeshCreate(parametricDim=dim1, spatialDim=spacedim, &
          nodeIDs=the_data%NdIDs, nodeCoords=the_data%NdCoords, &
          nodeOwners=the_data%NdOwners, elementIDs=the_data%ElIDs, &
          elementTypes=the_data%ElTypes, elementConn=the_data%ElConnect, &
          rc=rc)

      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
          line=__LINE__, &
          file=__FILE__)) &
          return  ! bail out

    end subroutine

   !> XYC added for structured grid:
    subroutine create_parallel_esmf_grid_from_griddata(the_data, out_esmf_grid)
      implicit none
      type(ESMF_Grid), intent(out)                  :: out_esmf_grid
      type(griddata), intent(in)                    :: the_data
      integer                                       :: rc

      ! THis fuction is 31.6.9. Create a Grid with user set edge connections and
      ! a regular distribution
      ! maxIndex specifies the dimension of grid: the upper extent of the grid
      ! array; 
      ! connflagDim1/2 = ESMF_GRIDCONN_NONE (default) without presence.
      ! coordSys = ESMF_COORDSYS_SPH_DEG (default) if not specified.
      ! But where did the coordinate information comes in??
     ! =============== another method to create grid code below: =================!
     ! out_esmf_grid=ESMF_GridCreate(maxIndex=the_data%maxIndex, connflagDim1=the_data%connflagDim1, &
      !           connflagDim2=the_data%connflagDim2, coordSys=the_data%coordSys,  rc=rc)

      ! call a function to put in the coordinate for this grid:
      out_esmf_grid=CreateGrid_ModelGrid(rc=rc)
      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
          line=__LINE__, &
          file=__FILE__)) &
          return  ! bail out


    end subroutine
    !-----------------------------------------------------------------------
    !- Sub !!!????
    !-----------------------------------------------------------------------

    subroutine read_config()
      character(ESMF_MAXPATHLEN)    :: fname ! config file name
      type(ESMF_Config)             :: cf     ! the Config itself
      integer                       :: rc

      rc = ESMF_SUCCESS

     !Initiate reading resource file
      cf = ESMF_ConfigCreate(rc=rc)  ! Create the empty Config
      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
        line=__LINE__, &
        file=__FILE__)) &
        return  ! bail out

      fname = "config.rc" ! Name the Resource File
      call ESMF_ConfigLoadFile(cf, fname, rc=rc) ! Load the Resource File
      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
        line=__LINE__, &
        file=__FILE__)) &
        return  ! bail out

     ! This subroutine is not used with NEMS system for time info reading. 
     ! Because the time interval information is passed via nems.configure file 
     ! with time slot definitation.
   
     ! read time coupling interval info
     ! call ESMF_ConfigGetAttribute(cf, atm_int, label="cpl_int:",default=300, rc=rc)
     ! call ESMF_ConfigGetAttribute(cf, atm_num, label="cpl_num:",default=0  , rc=rc)
     ! call ESMF_ConfigGetAttribute(cf, atm_den, label="cpl_den:",default=1  , rc=rc)
     ! if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
     !   line=__LINE__, &
     !   file=__FILE__)) &
     !   return  ! bail out

      call ESMF_ConfigGetAttribute(cf, atm_dir, label="atm_dir:",default='atm_inp/'  , rc=rc)
      call ESMF_ConfigGetAttribute(cf, atm_nam, label="atm_nam:", &
           default='atmesh.Constant.YYYYMMDD_sxy.nc'  , rc=rc)
      ! XYC added to indicate mesh type:
      call ESMF_ConfigGetAttribute(cf, atm_grd,label="atm_grd:", & 
                                       default='unstructured',rc=rc)
      if (ESMF_LogFoundError(rcToCheck=rc, msg=ESMF_LOGERR_PASSTHRU, &
        line=__LINE__, &
        file=__FILE__)) &
        return  ! bail out
      
      call ESMF_ConfigDestroy(cf, rc=rc) ! Destroy the Config
    end subroutine read_config


    !-----------------------------------------------------------------------
    !- Sub !!!????
    !-----------------------------------------------------------------------
!    !
!    !> \author Ali Samii - 2016
!    !! See: https://github.com/samiiali
!    !> @details Using the data available in <tt> fort.14, fort.18, partmesh.txt</tt> files
!    !! this function extracts the scalars and arrays required for construction of a
!    !! meshdata object.
!    !! After calling this fucntion, one can call create_parallel_esmf_mesh_from_meshdata()
!    !! or create_masked_esmf_mesh_from_data() to create an ESMF_Mesh.
!    !! @param vm This is an ESMF_VM object, which will be used to obtain the \c localPE
!    !! and \c peCount of the \c MPI_Communicator.
!    !! @param global_fort14_dir This is the directory path (relative to the executable
!    !! or an absolute path) which contains the global \c fort.14 file (not the fort.14
!    !! after decomposition).
!    !! @param the_data This is the output meshdata object.
!    !!
!    subroutine extract_parallel_data_from_mesh(global_fort14_dir, the_data,localPet)
!        implicit none
!        type(meshdata), intent(inout)         :: the_data
!        character(len=*), intent(in)          :: global_fort14_dir
!        character(len=200)                    :: partmesh_filename
!        integer, intent(in)                   :: localPet
!        integer                               :: i1, j1, i_num, num_global_nodes,io,garbage2
!        integer, allocatable                  :: local_node_numbers(:), local_elem_numbers(:), node_owner(:)
!        integer, parameter                    :: dim1=2, NumND_per_El=3
!
!    print *,"ATMESHm ..1.............................................. >> "
!        the_data%NumNd = np
!        the_data%NumEl = ne
!        allocate(the_data%NdIDs(the_data%NumNd))
!        allocate(local_node_numbers(the_data%NumNd))
!        allocate(the_data%ElIDs(the_data%NumEl))
!        allocate(local_elem_numbers(the_data%NumEl))
!        allocate(the_data%NdCoords(dim1*the_data%NumNd))
!        allocate(the_data%bathymetry(the_data%NumNd))
!        allocate(the_data%ElConnect(NumND_per_El*the_data%NumEl))
!        allocate(the_data%NdOwners(the_data%NumNd))
!        allocate(the_data%ElTypes(the_data%NumEl))
!    print *,"ATMESHm ..2.............................................. >> "
!        local_elem_numbers = IMAP_EL_LG
!        the_data%ElIDs = abs(local_elem_numbers)
!        local_node_numbers = NODES_LG
!        the_data%NumOwnedND = 0
!    print *,"ATMESHm ..3.............................................. >> "
!        do i1 = 1, the_data%NumNd, 1
!            if (local_node_numbers(i1) > 0) then
!                the_data%NumOwnedND = the_data%NumOwnedND + 1
!            end if
!        end do
!        the_data%NdIDs = abs(local_node_numbers)
!        allocate(the_data%owned_to_present_nodes(the_data%NumOwnedND))
!    print *,"ATMESHm ..4............................................. >> "
!        !> @details Read partmesh file to get global node information
!        !print *, 'size local_elem_numbers', size(local_elem_numbers),size(IMAP_EL_LG)
!        !print *, 'size local_node_numbers', size(local_node_numbers),size(NODES_LG)
!
!        !partmesh_filename = trim(global_fort14_dir//"/partmesh.txt")
!        open(unit=10099, file = TRIM(global_fort14_dir)//'/'//'partmeshw.txt', &
!            form='FORMATTED', status='OLD', action='READ')
!
!        !! Very ugly way of finding global element numebr
!        !! TODO: Saeed: need to find the reprsentive value for this
!        num_global_nodes = 0
!        do
!            read(unit=10099,fmt=*,iostat=io) garbage2
!            if (io/=0) exit
!            num_global_nodes = num_global_nodes + 1
!        end do
!        rewind(unit=10099)
!        !
!        !print *, 'size num_global_nodes', num_global_nodes,localPet
!
!        allocate(node_owner(num_global_nodes))
!        read(unit=10099, fmt=*) node_owner
!        close(10099)
!
!        do i1 = 1, the_data%NumNd, 1
!                the_data%NdCoords((i1-1)*dim1 + 1) = slam(i1)
!                the_data%NdCoords((i1-1)*dim1 + 2) = sfea(i1)
!        end do
!        do i1 = 1, the_data%NumEl, 1
!                the_data%ElConnect((i1-1)*NumND_per_El+1) = nm (i1,1)
!                the_data%ElConnect((i1-1)*NumND_per_El+2) = nm (i1,2)
!                the_data%ElConnect((i1-1)*NumND_per_El+3) = nm (i1,3)
!        end do
!
!        do i1= 1, the_data%NumNd, 1
!            the_data%NdOwners(i1) = node_owner(the_data%NdIDs(i1)) - 1
!        end do
!
!        j1 = 0
!        do i1 = 1, the_data%NumNd, 1
!            if (the_data%NdOwners(i1) == localPet) then
!                j1 = j1 + 1
!                the_data%owned_to_present_nodes(j1) = i1
!            end if
!        end do
!        the_data%ElTypes = ESMF_MESHELEMTYPE_TRI
!
!        !TODO: Saeed: Check if I need to dealocate arrays here!
!
!
!    end subroutine extract_parallel_data_from_mesh
!!
!
!    subroutine extract_parallel_data_from_mesh_orig(global_fort14_dir, the_data,localPet)
!        implicit none
!
!        type(meshdata), intent(inout)         :: the_data
!        character(len=*), intent(in)          :: global_fort14_dir
!        integer, intent(in)                   :: localPet
!        character(len=6)                      :: PE_ID, garbage1
!        
!        character(len=200)                    :: fort14_filename, fort18_filename, partmesh_filename
!        integer                               :: i1, j1, i_num, petCount, num_global_nodes, garbage2, garbage3
!        integer, allocatable                  :: local_node_numbers(:), local_elem_numbers(:), node_owner(:)
!        integer, parameter                    :: dim1=2, NumND_per_El=3
!
!        write(PE_ID, "(A,I4.4)") "WE", localPet
!        fort14_filename = TRIM(global_fort14_dir)//'/'//PE_ID//"/fort.14"
!        fort18_filename = TRIM(global_fort14_dir)//'/'//PE_ID//"/fort.18"
!        partmesh_filename = TRIM(global_fort14_dir)//'/'//'partmeshw.txt'
!
!
!        
!
!        open(unit=23414, file=fort14_filename, form='FORMATTED', status='OLD', action='READ')
!        open(unit=23418, file=fort18_filename, form='FORMATTED', status='OLD', action='READ')
!        open(unit=234100, file=partmesh_filename, form='FORMATTED', status='OLD', action='READ')
!
!        read(unit=23414, fmt=*)
!        read(unit=23414, fmt=*) the_data%NumEl, the_data%NumNd
!        allocate(the_data%NdIDs(the_data%NumNd))
!        allocate(local_node_numbers(the_data%NumNd))
!        allocate(the_data%ElIDs(the_data%NumEl))
!        allocate(local_elem_numbers(the_data%NumEl))
!        allocate(the_data%NdCoords(dim1*the_data%NumNd))
!        allocate(the_data%bathymetry(the_data%NumNd))
!        allocate(the_data%ElConnect(NumND_per_El*the_data%NumEl))
!        allocate(the_data%NdOwners(the_data%NumNd))
!        allocate(the_data%ElTypes(the_data%NumEl))
!
!        read(unit=23418, fmt=*)
!        read(unit=23418, fmt=*)
!        read(unit=23418, fmt=*) local_elem_numbers
!        the_data%ElIDs = abs(local_elem_numbers)
!        read(unit=23418, fmt=*) garbage1, num_global_nodes, garbage2, garbage3
!        read(unit=23418, fmt=*) local_node_numbers
!        the_data%NumOwnedND = 0
!        do i1 = 1, the_data%NumNd, 1
!            if (local_node_numbers(i1) > 0) then
!                the_data%NumOwnedND = the_data%NumOwnedND + 1
!            end if
!        end do
!        the_data%NdIDs = abs(local_node_numbers)
!        allocate(node_owner(num_global_nodes))
!        allocate(the_data%owned_to_present_nodes(the_data%NumOwnedND))
!        read(unit=234100, fmt=*) node_owner
!
!        do i1 = 1, the_data%NumNd, 1
!            read(unit=23414, fmt=*) local_node_numbers(i1), &
!                the_data%NdCoords((i1-1)*dim1 + 1), &
!                the_data%NdCoords((i1-1)*dim1 + 2), &
!                the_data%bathymetry(i1)
!        end do
!        do i1 = 1, the_data%NumEl, 1
!            read(unit=23414, fmt=*) local_elem_numbers(i1), i_num, &
!                the_data%ElConnect((i1-1)*NumND_per_El+1), &
!                the_data%ElConnect((i1-1)*NumND_per_El+2), &
!                the_data%ElConnect((i1-1)*NumND_per_El+3)
!        end do
!
!        do i1= 1, the_data%NumNd, 1
!            the_data%NdOwners(i1) = node_owner(the_data%NdIDs(i1)) - 1
!        end do
!
!        j1 = 0
!        do i1 = 1, the_data%NumNd, 1
!            if (the_data%NdOwners(i1) == localPet) then
!                j1 = j1 + 1
!                the_data%owned_to_present_nodes(j1) = i1
!            end if
!        end do
!        the_data%ElTypes = ESMF_MESHELEMTYPE_TRI
!
!        close(23414)
!        close(23418)
!        close(234100)
!    end subroutine extract_parallel_data_from_mesh_orig
!


end module
