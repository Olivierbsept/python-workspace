import win32com.client
from datetime import datetime
import pytz

# Ouvrir Outlook
outlook = win32com.client.Dispatch("Outlook.Application")
namespace = outlook.GetNamespace("MAPI")

# Accéder au calendrier
calendar = namespace.GetDefaultFolder(9)

# Heure actuelle
now = datetime.now(pytz.utc)

# Récupérer les éléments
appointments = calendar.Items
appointments.IncludeRecurrences = True
appointments.Sort("[Start]")

# Chercher la prochaine réunion
for appointment in appointments:

    start = appointment.Start.replace(tzinfo=pytz.utc)

    if start > now:  # réunion future
        print("Prochaine réunion :")
        print(f"Sujet : {appointment.Subject}")
        print(f"Début : {appointment.Start}")
        print(f"Fin : {appointment.End}")
        print(f"Lieu : {appointment.Location}")
        print("-" * 20)
        break