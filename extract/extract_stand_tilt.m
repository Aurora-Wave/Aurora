function [Analysis, DataSFieldName, errorflag, errormessage] = extract_stand_tilt (file_path, Which_orthostasis, Orthostatic_Files, Orthostatic_strings) 

%set defaults
    errorflag = false;
    errormessage = "";
    DataSFieldName ='undefined';

    try 
          Data = readtable(file_path);
          stand_15s_rri = round(Data.RRI_Value(15)*1000, 0);
          stand_30s_rri = round(Data.RRI_Value(30)*1000, 0);
          stand_3015_ratio = round(stand_30s_rri/stand_15s_rri,2);

                  
          %nadir SBP, and associated hemodynamics at this beat
          Time = Data.Ref_RValue-Data.Ref_RValue(1);
          NadirI = Time < 60;
          [stand_nadir_sbp, SNI] = min(Data.SAP_Value(NadirI)); %sytolic bp nadir index
          stand_nadir_sbp = round(stand_nadir_sbp, 0);
          stand_nadir_dbp = round(Data.DAP_Value(SNI), 0);
          stand_nadir_time = round(Time(SNI),1);
          stand_nadir_hr = round(60/Data.RRI_Value(SNI), 0);
          stand_nadir_co = round(Data.CO_Median(SNI), 2);
          stand_nadir_sv = round(Data.SV_Median(SNI), 0);
          stand_nadir_svr = round(Data.SVR_Median(SNI), 0);
         stand_nadir_etco2 = round(Data.ETCO2_Value(SNI), 0); %new
         stand_nadir_perO2 = round(Data.O2_Value(SNI), 0);
         stand_nadir_perCO2 = round(Data.CO2_Value(SNI), 0);
          
          %peak HR following nadir sbp
          
          PeakHRSearchI = SNI:find(NadirI, 1, 'last');
          [MinRRIearly, PeakHRearlyBeatI] = min(Data.RRI_Value(PeakHRSearchI));
          MinRRIearly = MinRRIearly(1);
          PeakHRearlyBeatI =PeakHRearlyBeatI(1);
          
          stand_pk_hr_60s = round(60/MinRRIearly, 0);
          
          PeakHRearlyBeatI = PeakHRearlyBeatI + SNI-1;
          stand_pk_hr_60s_sbp = round(Data.SAP_Value(PeakHRearlyBeatI), 0);
          stand_pk_hr_60s_dbp = round(Data.DAP_Value(PeakHRearlyBeatI), 0);
          stand_pk_hr_60s_co = round(Data.CO_Median(PeakHRearlyBeatI), 2);
          stand_pk_hr_60s_sv = round(Data.SV_Median(PeakHRearlyBeatI), 0);
          stand_pk_hr_60s_svr = round(Data.SVR_Median(PeakHRearlyBeatI), 0);
          stand_peak_hr_afternadirsbp = round(60/MinRRIearly, 0);
          stand_pk_hr_60s_time = round(Time(PeakHRearlyBeatI),1);
          stand_pk_hr_60s_etco2 = round(Data.ETCO2_Value(PeakHRearlyBeatI), 0); %new
          stand_pk_hr_60s_perO2 = round(Data.O2_Value(PeakHRearlyBeatI), 0);
          stand_pk_hr_60s_perCO2 = round(Data.CO2_Value(PeakHRearlyBeatI), 0);
          %Peak HR following 5 min standing
          
          LatePeakHRI = Time > 5*60;
          
          [MinRRILate, TimetoPeakHRAfter5minI] = min(Data.RRI_Value(LatePeakHRI));
          stand_pk_hr_last5m = round(60/MinRRILate, 0);
          stand_pk_hr_last5m_time = round(Time(TimetoPeakHRAfter5minI+find(LatePeakHRI,1)-1)/60, 1);
          
          %hemodynamics at 20s, 30s, 40s, 50s
          
          %identify index for each time
          I20 = find(Time > 20,1);
          I30 = find(Time > 30,1);
          I40 = find(Time > 40,1);
          I50 = find(Time > 50,1);
          
          
          %HR
          stand_20s_hr = round(60/Data.RRI_Value(I20), 0);
          stand_30s_hr = round(60/Data.RRI_Value(I30), 0);
          stand_40s_hr = round(60/Data.RRI_Value(I40), 0);
          stand_50s_hr = round(60/Data.RRI_Value(I50), 0);
          
          %SBP
          stand_20s_sbp = round(Data.SAP_Value(I20), 0);
          stand_30s_sbp = round(Data.SAP_Value(I30), 0);
          stand_40s_sbp = round(Data.SAP_Value(I40), 0);
          stand_50s_sbp = round(Data.SAP_Value(I50), 0);
          
          %DBP
          stand_20s_dbp = round(Data.DAP_Value(I20), 0);
          stand_30s_dbp = round(Data.DAP_Value(I30), 0);
          stand_40s_dbp = round(Data.DAP_Value(I40), 0);
          stand_50s_dbp = round(Data.DAP_Value(I50), 0);
          
          %CO
          stand_20s_co = round(Data.CO_Median(I20), 2);
          stand_30s_co = round(Data.CO_Median(I30), 2);
          stand_40s_co = round(Data.CO_Median(I40), 2);
          stand_50s_co = round(Data.CO_Median(I50), 2);
          
          %SV
          stand_20s_sv = round(Data.SV_Median(I20), 0);
          stand_30s_sv = round(Data.SV_Median(I30), 0);
          stand_40s_sv = round(Data.SV_Median(I40), 0);
          stand_50s_sv = round(Data.SV_Median(I50), 0);
          
          %SVR
          stand_20s_svr = round(Data.SVR_Median(I20), 0);
          stand_30s_svr = round(Data.SVR_Median(I30), 0);
          stand_40s_svr = round(Data.SVR_Median(I40), 0);
          stand_50s_svr = round(Data.SVR_Median(I50), 0);

          %ETCO2 %new
          stand_20s_etco2 = round(Data.ETCO2_Value(I20), 0);
          stand_30s_etco2 = round(Data.ETCO2_Value(I30), 0);
          stand_40s_etco2 = round(Data.ETCO2_Value(I40), 0);
          stand_50s_etco2 = round(Data.ETCO2_Value(I50), 0);

          %O2
          stand_20s_perO2 = round(Data.O2_Value(I20), 0);
          stand_30s_perO2 = round(Data.O2_Value(I30), 0);
          stand_40s_perO2 = round(Data.O2_Value(I40), 0);
          stand_50s_perO2 = round(Data.O2_Value(I50), 0);

          %CO2
          stand_20s_perCO2 = round(Data.CO2_Value(I20), 0);
          stand_30s_perCO2 = round(Data.CO2_Value(I30), 0);
          stand_40s_perCO2 = round(Data.CO2_Value(I40), 0);
          stand_50s_perCO2 = round(Data.CO2_Value(I50), 0);
          
          
          %Peak HR in first 60 seconds
          First60I = 1:find(Time > 60,1)-1;
          [minRRI_first60s, min_first60_I] = min(Data.RRI_Value(First60I));
          stand_peak_hr_first60s = round(60/minRRI_first60s, 0);
          stand_timetopeakhr_first60s = round(Time(min_first60_I), 1);
          
          
          %Hemodynamics from minutes 5-10 of standing
          IOver5min = find(Time > 300 & Time < 600);
          
          stand_pk_sbp_last5m         = round(max(Data.SAP_Value(IOver5min)), 0);
          stand_pk_dbp_last5m         = round(max(Data.DAP_Value(IOver5min)), 0);
          stand_pk_co_last5m          = round(max(Data.CO_Median(IOver5min)), 2);
          stand_pk_sv_last5m          = round(max(Data.SV_Median(IOver5min)), 0);
          stand_pk_svr_last5m         = round(max(Data.SVR_Median(IOver5min)), 0);
          stand_pk_etco2_last5m         = round(max(Data.ETCO2_Value(IOver5min)), 0);
          stand_pk_perO2_last5m         = round(max(Data.O2_Value(IOver5min)), 0);
          stand_pk_perCO2_last5m         = round(max(Data.CO2_Value(IOver5min)), 0);
          
          Analysis = table(...
            stand_nadir_time,... 
            stand_nadir_sbp,...
            stand_nadir_dbp,...
            stand_nadir_hr,...
            stand_nadir_co,...
            stand_nadir_sv,...
            stand_nadir_svr,...
            stand_nadir_etco2,...
            stand_15s_rri,...
            stand_30s_rri,...
            stand_pk_hr_last5m_time,... %in minutes
            stand_3015_ratio,...
            stand_20s_sbp,...
            stand_30s_sbp,...
            stand_40s_sbp,...
            stand_50s_sbp,...
            stand_20s_dbp,...
            stand_30s_dbp,...
            stand_40s_dbp,...
            stand_50s_dbp,...
            stand_20s_co,...
            stand_30s_co,...
            stand_40s_co,...
            stand_50s_co,...
            stand_20s_sv,...
            stand_30s_sv,...
            stand_40s_sv,...
            stand_50s_sv,...
            stand_20s_svr,...
            stand_30s_svr,...
            stand_40s_svr,...
            stand_50s_svr,...
            stand_20s_hr,...
            stand_30s_hr,...
            stand_40s_hr,...
            stand_50s_hr,...
            stand_20s_etco2,... %new
            stand_30s_etco2,...
            stand_40s_etco2,...
            stand_50s_etco2,...
            stand_pk_hr_60s_sbp,...
            stand_pk_hr_60s_dbp,...
            stand_pk_hr_60s_co,...
            stand_pk_hr_60s_sv,...
            stand_pk_hr_60s_svr,...
            stand_pk_hr_60s,...
            stand_pk_hr_60s_time,...
            stand_pk_hr_60s_etco2,...
            stand_pk_sbp_last5m,...        
            stand_pk_dbp_last5m,...        
            stand_pk_co_last5m,...         
            stand_pk_sv_last5m,...         
            stand_pk_svr_last5m,...
            stand_pk_etco2_last5m,...
            stand_nadir_perO2,...
            stand_nadir_perCO2,...
            stand_pk_hr_60s_perO2,...
            stand_pk_hr_60s_perCO2,...
            stand_20s_perO2,...
            stand_30s_perO2,...
            stand_40s_perO2,...
            stand_50s_perO2,...
            stand_20s_perCO2,...
            stand_30s_perCO2,...
            stand_40s_perCO2,...
            stand_50s_perCO2,...
            stand_pk_perO2_last5m,...
            stand_pk_perCO2_last5m   );
           %Removed from above: stand_pk_hr_last5m - now calculated from
           %summary data
        
            %Define table column names
            VarNames = Analysis.Properties.VariableNames;
            
            %Index of which orthostatic test was performed
            Which_orthostasis_I = find(strcmp(Orthostatic_strings, Which_orthostasis));
           
            
            switch Which_orthostasis
                case 'Stand'
                    %default variable names begin with 'stand_', so 
                    %no action needed to change the VarNames
                    DataSFieldName = 'StandAnalysis';
                       
                case 'Tilt'
                    DataSFieldName = 'TiltAnalysis';
                    
                    orth_label = 'tilt_';
                    VarNames = strrep(VarNames, 'stand_', orth_label); %Change variable names
                    
                case 'LBNP'
                    DataSFieldName = 'LBNPAnalysis';

                    orth_label = 'lbnp_';
                    VarNames = strrep(VarNames, 'stand_', orth_label);%Change variable names
                    
            end
          
            %Update Variable names in table
            Analysis.Properties.VariableNames = VarNames;
           
            
            % Update the "Orthostatic_Files" struct
            Orthostatic_Files.Ortho_DataSFieldName(Which_orthostasis_I) = DataSFieldName;
            Orthostatic_Files.Ortho_FileName(Which_orthostasis_I) = file_path;


    catch ME
        Analysis = table();
        errorflag = true;
        errormessage = ME.message;  
            

    end


end
