% NOTE: Requires mapping toolbox to write shapefile
function ASGS_fort22_to_PWM_inputs(track_only)
    fno = 'fort.22';
    fid = fopen(fno);

    r = 0;
    while ~feof(fid)
        tline = fgetl(fid);
        S0 = split(tline,',') ;      
        r = r + 1;
        nc = length(S0);  
     
        for i = 1:nc
            A{r,i} = strtrim(char(S0{i})); %#ok<AGROW>
        end           
        if nc < 37               
            for i = (nc + 1):37          
                A{r,i} = '0';
            end
        end           
    end
    sn = char(A(1,2));  % storm number 
    B = cell2mat(A(:,3));

    %%  datetime - find forecast time (latest time -end of file)
    B2 = zeros(length(B),5);
    for i = 1:length(B)
        B2(i,1) = str2double(B(i,1:4));
        B2(i,2) = str2double(B(i,5:6));
        B2(i,3) = str2double(B(i,7:8));
        B2(i,4) = str2double(B(i,9:10));
        B2(i,5) = 0;
    end

    B3 = datetime(B2(:,1),B2(:,2),B2(:,3),B2(:,4),B2(:,5),0);
    [~,ia,~] = unique(B3);
    str1 = 'NHC';
    str2 = ['A' pad(sn,2,'left','0')];
    str3 = 'URIPWMIN';
    x = [str1 ' ' str2 ' ' str3 '  '];

    len_ia = length(ia);
    As2 = cell(len_ia,6);
    for i = 1:len_ia
        r = ia(i); 
        As2{i,1} = str1;
        As2{i,2} = str2;
        As2{i,3} = [pad(num2str(B2(r,1)),2,'left','0') pad(num2str(B2(r,2)),2,'left','0') pad(num2str(B2(r,3)),2,'left','0')]; 
        As2{i,4} = [pad(num2str(B2(r,4)),2,'left','0') pad(num2str(B2(r,5)),2,'left','0')];
        As2{i,5} = A{r,7};
        As2{i,6} = A{r,8};     
    end
    As = As2;

    [LL] = trackll_2num(As(:,[5 6]));
    for i = 1:(length(LL) - 1)
        LL(i,3) = azimuth('gc',LL(i,1),LL(i,2),LL(i + 1,1),LL(i + 1,2));
    end
    LL(end,3)=LL((end - 1),3);

    if ~track_only
        ys = num2str(B2(1,1)); 
        ms = pad(num2str(B2(1,2)),2,'left','0'); 
        ds = pad(num2str(B2(1,3)),2,'left','0'); 
        hrs = pad(num2str(B2(1,4)),2,'left','0'); 
        mis = pad(num2str(B2(1,5)),2,'left','0'); 
        secs = '00';
        stds = [ys ' ' ms ' ' ds ' ' hrs ' ' mis ' ' secs];
        dura = B3(ia(end)) - B3(ia(1));

        Ad2 = zeros(len_ia,15);
        Rmwo = zeros(len_ia,1);
        for i = 1:len_ia
            r = ia(i);   
            Ad2(i,1) = 0;
            Ad2(i,2) = 0;
            Ad2(i,3) = str2double(cell2mat(A(r,10)));
            Ad2(i,4) = 1014;
            Ad2(i,5) = 1014;    
            Ad2(i,6) = round(str2double(cell2mat(A(r,9))) * 0.514444,0);  % max wind speed in m/s
            
            temp = str2double(cell2mat(A(r,19)));
            if temp > 0
                Ad2(i,7) = round(temp * 1.852,0);  % radius of last closed isobar - converted to km
            else
                Ad2(i,7) = 99; 
            end
            
            temp = str2double(cell2mat(A(r,20)));
            if temp > 0
                Rmwo(i) = round(temp * 1.852,0);  % radius of maximum winds
            else
                Rmwo(i) = -99; 
            end
            
            Ad2(i,8) = round(str2double(cell2mat(A(r,14))) * 1.852,0);  % radiii in km (original file is nm)
            Ad2(i,9) = round(str2double(cell2mat(A(r,15))) * 1.852,0);  
            Ad2(i,10) = round(str2double(cell2mat(A(r,16))) * 1.852,0);  
            Ad2(i,11) = round(str2double(cell2mat(A(r,17))) * 1.852,0);  
                                
            ind = find(B3 == B3(r));
            if length(ind) > 1
                Ad2(i,12) = round(str2double(cell2mat(A(r + 1,14))) * 1.852,0);
                Ad2(i,13) = round(str2double(cell2mat(A(r + 1,15))) * 1.852,0);  
                Ad2(i,14) = round(str2double(cell2mat(A(r + 1,16))) * 1.852,0);  
                Ad2(i,15) = round(str2double(cell2mat(A(r + 1,17))) * 1.852,0);
            else
                Ad2(i,12) = 0;
                Ad2(i,13) = 0;
                Ad2(i,14) = 0;
                Ad2(i,15) = 0;  
            end
        end

        if exist('Wind_Inp.txt', 'file')
            delete 'Wind_Inp.txt'
        end
        fnw = 'Wind_Inp.txt';  % output file name
        fid = fopen(fnw,'w');
        tn = 'richamp';
        fprintf(fid,'%s \n',tn);
        fprintf(fid,'%s \n','3');
        fprintf(fid,'%s \n',stds);
        fprintf(fid,'%s \n','1.0');
        fprintf(fid,'%s \n',num2str(hours(dura)));
        fprintf(fid,'%s \n','-101.0 -49.0');
        fprintf(fid,'%s \n','4.0  51.');
        fprintf(fid,'%s \n','12.');
        fclose(fid);

        fno = ['track.' tn];  % output file name
        Ad = Ad2;
        sz = size(As);
        At = zeros(sz(1),6);
        for i = 1:sz(1)
            dd = char(As(i,3));
            y = dd(1:4);
            m = dd(5:6);
            if m(1) == '0'
                m = m(2);
            end
           
            d = dd(7:8);
            if d(1) == '0'
                d = d(2);
            end     
            
            dd = char(As(i,4));
            hh = dd(1:2);
            if dd(1) == '0'
                hh = dd(2);
            end
            mm = dd(3:4);
                  
            At(i,1) = str2double(y);
            At(i,2) = str2double(m);
            At(i,3) = str2double(d);
            At(i,4) = str2double(hh);
            At(i,5) = str2double(mm);
            At(i,6) = 0;    
        end

        %% Radius of max winds
        % if not specified - calculated %Rmax = exp(2.636 - ((0.00005086 * (dP ^ 2)) + 0.0394899 * latitude)) 
        dP = Ad(:,4) - Ad(:,3);
        
        len_rmwo = length(Rmwo);
        Rmx_c1 = zeros(len_rmwo,1);
        Rmx_c2 = zeros(len_rmwo,1);
        Rmx_c3 = zeros(len_rmwo,1);
        Rmxc = zeros(len_rmwo,1);
        for i = 1:len_rmwo
            if Rmwo(i) == -99
                Rmx_c1(i) = 0.00005086 * (dP(i) .^ 2);
                Rmx_c2(i) = 0.0394899 * (LL(i,1));
                Rmx_c3(i) = 2.636 - Rmx_c1(i) + Rmx_c2(i);
                Rmxc(i) = exp(Rmx_c3(i));     
            else
                Rmxc(i) = Rmwo(i);    
            end    
        end
        
        %% radius of closure (pressure)
        Ra = zeros(length(Ad(:,7)),1);
        for i = 1:length(Ad(:,7))
            if Ad(i,7) == 99
                Ra(i) = fix(Rmxc(i) * 20);
            else
                Ra(i) = Ad(i,7);
            end
        end

        fid = fopen(fno,'w');
        for n = 1:sz(1)
            str4 = char(As(n,3));  % date
            str5 = char(As(n,4));  % time
            str6 = char(As(n,5));  % lat
            str7a = char(As(n,6));  % lon
            if length(str7a) == 4
                str7 = ['0' str7a];
            else
                str7 = str7a;
            end       
            str8 = pad(num2str(fix(LL(n,3))),3,'left','0');  % heading  
            str9 = pad(num2str(Ad(n,3)),4,'left','0');  % low pres
            str10 = pad(num2str(Ad(n,4)),4,'left','0');  % high pres
            str11 = pad(num2str(Ra(n)),4,'left','0');  % closure radius (20x)  
            str12 = pad(num2str(Ad(n,6)),2,'left','0');  % mx ws m/s
            %% requires logic to automate - I have been mannually selecting
            %str13 = pad(num2str(Ad(n,7)),3,'left','0');  % radius of maximum winds km from input
            str13 = pad(num2str(fix(Rmxc(n))),3,'left','0');  % radius of maximum winds km calculated  

            if Ad(n,8) == 0
                Ad(n,8) = -999;
            end
            str14a = pad(num2str(Ad(n,8)),4,'left','0');  %34kt NE 
            if Ad(n,9) == 0
                Ad(n,9)=-999;
            end
            str14b = pad(num2str(Ad(n,9)),4,'left','0');  % 34kt SE
            if Ad(n,10) == 0
                Ad(n,10) = -999;
            end 
            str14c = pad(num2str(Ad(n,10)),4,'left','0');  % 34kt SW
            if Ad(n,11) == 0
                Ad(n,11) = -999;
            end 
            str14d = pad(num2str(Ad(n,11)),4,'left','0');  % 34kt NW
            strL = 'D';
            if Ad(n,12) == 0
                Ad(n,12) = -999;
            end
            str15a = pad(num2str(Ad(n,12)),4,'left','0');  % 50kt NE
            if Ad(n,13) == 0
                Ad(n,13) = -999;
            end 
            str15b = pad(num2str(Ad(n,13)),4,'left','0');  % 50kt SE
            if Ad(n,14) == 0
                Ad(n,14) = -999;
            end 
            str15c = pad(num2str(Ad(n,14)),4,'left','0');  % 50kt SW
            if Ad(n,15) == 0
                Ad(n,15) = -999;
            end
            str15d = pad(num2str(Ad(n,15)),4,'left','0');  % 50kt NW
            
            fprintf(fid,'%s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s %s\n',x,str4,str5,str6,str7,str8,str9,str9,str10,str11,str12,str13,str14a,str14b,str14c,str14d,strL,str15a,str15b,str15c,str15d);
        end
        fclose(fid);
        
        %% write out time, pressure and radius of max winds
        fnp = 'TrackRMW.txt';
        fid = fopen(fnp,'w');
        fprintf(fid,'%s\n','Yr, Mo, Day, Hr, Min, Sec, Central P(mbar), Background P(mbar), Radius of Max Winds (km)');
        for n = 1:sz(1)  
            fprintf(fid,'%s %s %s %s %s %s %s %s %s\n',num2str(At(n,1)),num2str(At(n,2)),num2str(At(n,3)),num2str(At(n,4)),num2str(At(n,5)),num2str(At(n,6)),num2str(Ad(n,3)),num2str(Ad(n,4)),num2str(Rmxc(n)));
        end
        fclose(fid);
    end

    %% write shapefile (requires mapping toolbox)
    Data.Geometry = 'Polyline' ;
    Data.X = LL(:,2)  ;  % latitude
    Data.Y = LL(:,1)  ;  % longitude
    Data.Name = 'TrackLine' ;   % attribute
    shapewrite(Data,'Track.shp')
end
