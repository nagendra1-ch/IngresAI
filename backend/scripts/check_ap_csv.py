import pandas as pd

df = pd.read_csv(r"c:\Users\chnag\OneDrive\Attachments\Desktop\ingres1\states\andhra_pradesh.csv")
guntur = df[df['district_name'].str.lower() == 'guntur']
print(guntur.head(1).to_dict(orient='records'))
