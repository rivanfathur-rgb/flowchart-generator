#include <iostream>
#include <iomanip>
using namespace std;

int main() {
    int a,b,c,d;
    cout << "PENJUMLAHAN MATRIKS" << endl << "MATRIKS A" << endl;
    cout << "Masukkan jumlah baris: ";
    cin >> a;
    cout << "Masukkan jumlah kolom: ";
    cin >> b;
    int A[10][10];
    for (int i = 0; i < a; i++) {
        for (int j = 0; j < b; j++) {
            cout << "Masukkan baris " << (i + 1) << " kolom " << (j + 1) << ": ";
            cin >> A[i][j];
        }
    }
    cout << "MATRIKS B" << endl;
    cout << "Masukkan jumlah baris: ";
    cin >> c;
    if (c != a) {
        cout << "Jumlah baris matriks B harus sama dengan jumlah baris matriks A." 
             << endl;
        return 1;
    }
    cout << "Masukkan jumlah kolom: ";
    cin >> d;
    if (d != b) {
        cout << "Jumlah kolom matriks B harus sama dengan jumlah kolom matriks A." 
             << endl;
        return 1;
    }
    int B[10][10];
    for (int i = 0; i < c; i++) {
        for (int j = 0; j < d; j++) {
            cout << "Masukkan baris " << (i + 1) << " kolom " << (j + 1) << ": ";
            cin >> B[i][j];
        }
    }
    int Hasil[10][10];
    for (int i = 0; i < a; i++) {
        for (int j = 0; j < b; j++) {
            Hasil[i][j] = A[i][j] + B[i][j];
        }
    }
    cout << "Hasil Penjumlahan Matriks:" << endl;
    for (int i = 0; i < a; i++) {
        cout << "|";
        for (int j = 0; j < b; j++) {
            cout << setw(4) << Hasil[i][j];
        }
        cout << "|" << endl;
    }
    return 0;
}