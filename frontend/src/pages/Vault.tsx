import {Input} from "@/components/ui/input";
import {ScrollArea} from "@/components/ui/scroll-area";
import {Skeleton} from "@/components/ui/skeleton";
import AddCreds from "@/components/vault/AddCreds";
import {VaultList} from "@/components/vault/VaultList";
import {useGetSecretsQuery, useLazyGetSecretQuery} from "@/services/vaultApi";
import {TSecret} from "@/types/vaultTypes";
import {Search} from "lucide-react";
import {useEffect, useState} from "react";

const {VITE_APP_VA_NAMESPACE} = import.meta.env;

export const Vault = () => {
  const [searchQuery, setSearchQuery] = useState("");
  const [secretsList, setSecretsList] = useState<TSecret[]>([]);
  const [filteredSecrets, setFilteredSecrets] = useState<TSecret[]>([]);
  const [isLoadingSecrets, setIsLoadingSecrets] = useState(false);

  useEffect(() => {
    const filtered = secretsList.filter((secret) =>
      secret.website.toLowerCase().includes(searchQuery.toLowerCase())
    );
    setFilteredSecrets(filtered);
  }, [searchQuery, secretsList]);

  const {
    data: secrets,
    isLoading: isLoadingSecretsList,
    fulfilledTimeStamp,
  } = useGetSecretsQuery(VITE_APP_VA_NAMESPACE, {
    refetchOnMountOrArgChange: true,
  });

  const [getSecret] = useLazyGetSecretQuery();

  useEffect(() => {
    const fetchAllSecrets = async () => {
      if (!secrets?.message) return;

      setIsLoadingSecrets(true);
      const secretsList = Array.isArray(secrets.message)
        ? secrets.message
        : Object.keys(secrets.message);

      const fetchedCredentials: TSecret[] = [];

      try {
        for (const secretKey of secretsList) {
          try {
            // Skip API key or sensitive credentials
            if (
              secretKey.includes("agentic_browser_key") ||
              secretKey.includes("browser_key")
            ) {
              continue;
            }

            const response = await getSecret({
              secret_key: secretKey,
              namespace: VITE_APP_VA_NAMESPACE,
            });

            if (response.status === "fulfilled") {
              const secretData = response.data;
              if (secretData.status === 200 && secretData.message) {
                let parsedCredential: {
                  website?: string;
                  username?: string;
                  password?: string;
                };

                try {
                  // Handle nested secret structure
                  if (
                    secretData.message.secret &&
                    typeof secretData.message.secret === "object" &&
                    secretKey in secretData.message.secret
                  ) {
                    // Parse the nested JSON string
                    parsedCredential = JSON.parse(
                      secretData.message.secret[
                        secretKey as keyof typeof secretData.message.secret
                      ]
                    );
                  } else if (typeof secretData.message === "string") {
                    // Handle direct string JSON
                    parsedCredential = JSON.parse(secretData.message);
                  } else {
                    // Handle direct object
                    parsedCredential = secretData.message;
                  }

                  // Validate credential structure
                  if (
                    parsedCredential.website &&
                    parsedCredential.username &&
                    parsedCredential.password
                  ) {
                    const existingCredential = fetchedCredentials.find(
                      (cred) => cred.website === parsedCredential.website
                    );

                    if (existingCredential) {
                      existingCredential.secrets = [];
                      existingCredential.secrets.push({
                        id: secretKey,
                        username: parsedCredential.username,
                        password: parsedCredential.password,
                      });
                    } else {
                      fetchedCredentials.push({
                        website: parsedCredential.website,
                        secrets: [
                          {
                            id: secretKey,
                            username: parsedCredential.username,
                            password: parsedCredential.password,
                          },
                        ],
                      });
                    }
                  }
                } catch (parseError) {
                  console.error(
                    `Failed to parse credential for ${secretKey}:`,
                    parseError
                  );
                }
              }
            }
          } catch (error) {
            console.error(`Error fetching secret ${secretKey}:`, error);
          }
        }

        setSecretsList(fetchedCredentials);
      } catch (error) {
        console.error("Failed to fetch credentials:", error);
      } finally {
        setIsLoadingSecrets(false);
      }
    };

    // Run whenever query is fulfilled, regardless of data changes
    if (fulfilledTimeStamp) {
      console.log("Fetching secrets, timestamp:", fulfilledTimeStamp);
      fetchAllSecrets();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fulfilledTimeStamp, getSecret]);

  return (
    <div className="p-8 space-y-6 w-[70%] mx-auto">
      <div className="space-y-2">
        <h1 className="text-3xl font-bold">Vault</h1>
        <p className="text-muted-foreground">
          Add, save and manage your passwords.
        </p>
        <p className="text-yellow-500 text-sm">
          ⚠️ Vault is an experimental feature. We're working to make it more
          secure.
        </p>
      </div>
      <div className="flex justify-between items-center gap-4 pr-3">
        <div className="relative w-full">
          <Input
            type="text"
            placeholder="Search for website in vault"
            className="bg-popover-secondary text-foreground px-10 py-2 rounded-sm w-full border border-border"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
        </div>
        <AddCreds />
      </div>
      <ScrollArea className="h-[60vh]">
        {isLoadingSecrets || isLoadingSecretsList ? (
          <div className="flex flex-col space-y-2 pr-3">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton className="h-12 w-full" key={i} />
            ))}
          </div>
        ) : (
          <VaultList secrets={filteredSecrets} />
        )}
      </ScrollArea>
    </div>
  );
};
